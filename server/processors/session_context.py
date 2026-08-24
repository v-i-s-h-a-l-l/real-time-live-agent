"""Receive generic tutoring session + active learning context from the browser.

Domain-agnostic: stores client payloads and injects short system notes into the
LLM context. Does not hardcode subjects or lesson pedagogy.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from pipecat.frames.frames import Frame, InputTransportMessageFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from protocol import (
    CLIENT_LEARNING_CONTEXT,
    CLIENT_SESSION_CONTEXT,
    CLIENT_TUTOR_CONTEXT,
    is_client_message,
)
from security import (
    sanitize_client_dict,
    tutor_context_signature_required,
    verify_tutor_context,
)

_SESSION_MARKER = "[SESSION_CONTEXT]"
_LEARNING_MARKER = "[LEARNING_CONTEXT]"

# Pure student-state turns (grant a break, let them leave, react to a joke)
# must not leak the slide identity. If the LLM can still see the topic name,
# the section title, the visible text, or the formulas in a [LEARNING_CONTEXT]
# block, it will keep appending "Let's stay on Euclid's Division Lemma…" to a
# reply that should just say "go grab something to eat."
_CONVERSATIONAL_LEARNING_NOTE = (
    f"{_LEARNING_MARKER} On-screen lesson content is withheld this turn — the "
    "tutor is having a brief human conversation about the student's state, "
    "not teaching. Do not name the topic, chapter, section, slide, lemma, "
    "theorem, or any formula. Do not quote or restate visible content. Do not "
    "offer to move Next. Do not say 'let's stay on…' or 'let's focus on…'. "
    "The lesson will resume on the next teaching turn from the last "
    "conversation. Do not invent lesson content either — if you don't have it "
    "in this turn, don't mention it."
)
_CONVERSATIONAL_SESSION_NOTE = (
    f"{_SESSION_MARKER} Study session frame withheld this turn. Respond to what "
    "the student actually said as a human tutor would. Do not name the current "
    "topic, chapter, or subject, and do not steer the conversation back to a "
    "specific lesson unless the chosen tutor action for this turn says so."
)


class SessionContextStore:
    """Mutable per-connection store for session + learning + tutor-only payloads."""

    def __init__(self) -> None:
        self.context: dict[str, Any] | None = None
        self.learning_context: dict[str, Any] | None = None
        self.tutor_context: dict[str, Any] | None = None
        self.tts_voice_id: str | None = None
        self.applied: bool = False
        # When True, the next LLM response is shown in the transcript but not spoken.
        self.skip_tts_next_response: bool = False

    def set_context(self, context: dict[str, Any]) -> None:
        self.context = dict(context)
        self.applied = False

    def set_learning_context(self, context: dict[str, Any]) -> None:
        self.learning_context = dict(context)

    def set_tutor_context(self, context: dict[str, Any]) -> None:
        self.tutor_context = dict(context)


def _system_note(context: dict[str, Any]) -> str:
    """Build a domain-agnostic study-context note for the LLM."""
    class_label = context.get("classLabel") or context.get("classId") or "unspecified class"
    subject = context.get("subjectName") or context.get("subjectId") or "unspecified subject"
    chapter = context.get("chapterTitle") or context.get("chapterId") or "unspecified chapter"
    topic = context.get("topicTitle") or context.get("topicId") or "unspecified topic"
    description = (context.get("topicDescription") or "").strip()
    objectives = context.get("learningObjectives") or []

    lines = [
        f"{_SESSION_MARKER} Study session context (provided by the client — stay on this topic unless the learner clearly pivots):",
        f"- Class: {class_label}",
        f"- Subject: {subject}",
        f"- Chapter: {chapter}",
        f"- Topic: {topic}",
    ]
    if description:
        lines.append(f"- Topic focus: {description}")
    if isinstance(objectives, list) and objectives:
        obj_text = "; ".join(str(o) for o in objectives[:6])
        lines.append(f"- Learning objectives: {obj_text}")
    lines.append(
        "Teach helpfully and briefly. Prefer guiding questions over dumping full answers. "
        "If the learner goes far off-topic, gently offer to return to this topic."
    )
    return "\n".join(lines)


def _learning_note(context: dict[str, Any]) -> str:
    """Student-visible active unit — must not include hidden solutions."""
    phase = context.get("phase") or "learning"
    topic = context.get("topicTitle") or context.get("topicId") or "current topic"
    progress = context.get("progressLabel") or ""

    lines = [
        f"{_LEARNING_MARKER} CURRENT ACTIVE LEARNING CONTEXT — this is the slide/section the student can see right now.",
        f"- Class: {context.get('classLabel') or context.get('classId') or 'Class 10'}",
        f"- Subject: {context.get('subjectName') or context.get('subjectId') or 'Mathematics'}",
        f"- Chapter: {context.get('chapterTitle') or context.get('chapterId') or 'current chapter'}",
        f"- Topic: {topic}",
        f"- Phase: {phase}",
    ]
    if progress:
        lines.append(f"- Progress: {progress}")

    if phase == "learning":
        section = context.get("sectionTitle") or context.get("sectionId")
        if section:
            lines.append(f"- Section: {section}")
        section_type = context.get("sectionType")
        if section_type:
            lines.append(f"- Section type: {section_type}")
        visible = (context.get("visibleContent") or "").strip()
        if visible:
            lines.append(f"- Visible content: {visible[:800]}")
        key_points = context.get("keyPoints") or []
        if isinstance(key_points, list) and key_points:
            lines.append(
                "- Key points: " + "; ".join(str(p) for p in key_points[:5])
            )
        formulas = context.get("formulas") or []
        if isinstance(formulas, list) and formulas:
            lines.append("- Formulas on screen: " + "; ".join(str(f) for f in formulas[:4]))
        lines.append(
            "If the student says 'this slide', 'this', 'the current topic', 'explain the slide', "
            "or 'what is this', they mean THIS section and the visible content above. "
            "Never ask which slide they are looking at."
        )
    elif phase == "practice":
        question = (context.get("question") or "").strip()
        if question:
            lines.append(f"- Practice question: {question}")
        difficulty = context.get("difficulty")
        if difficulty:
            lines.append(f"- Difficulty: {difficulty}")
        hint_count = context.get("hintCount")
        if hint_count is not None:
            lines.append(f"- Hints available to student: {hint_count}")
        lines.append(
            "Do not reveal the full solution unless the student asks for help after trying. "
            "Guide with questions and hints first."
        )
    elif phase == "completed":
        lines.append("- The student has finished the lesson sequence.")

    lines.append(
        "Ground answers in this on-screen unit. If helpful, invite the student to move Next "
        "when they are ready."
    )
    return "\n".join(lines)


def conversational_learning_note() -> str:
    """Placeholder for [LEARNING_CONTEXT] on a purely conversational turn."""
    return _CONVERSATIONAL_LEARNING_NOTE


def conversational_session_note() -> str:
    """Placeholder for [SESSION_CONTEXT] on a purely conversational turn."""
    return _CONVERSATIONAL_SESSION_NOTE


def scoped_learning_note(context: dict[str, Any]) -> str:
    """Compact [LEARNING_CONTEXT] for scope-holding turns.

    Keeps the topic and section name so the tutor can say "we're on Euclid's
    Division Lemma, that's later" naturally. Drops the visible slide text, the
    formulas on screen, and the "Ground answers / Invite Next" tail — none of
    that belongs in a redirect.
    """
    class_label = context.get("classLabel") or context.get("classId") or "Class 10"
    subject = context.get("subjectName") or context.get("subjectId") or "Mathematics"
    topic = context.get("topicTitle") or context.get("topicId") or "current topic"
    section = context.get("sectionTitle") or context.get("sectionId")

    lines = [
        f"{_LEARNING_MARKER} Scope frame only — the student is trying to leave "
        "this lesson. Keep the anchor visible, do not teach.",
        f"- Class: {class_label}",
        f"- Subject: {subject}",
        f"- Current topic: {topic}",
    ]
    if section:
        lines.append(f"- Current section: {section}")
    lines.append(
        "- Slide text, formulas, and next-step invitation are withheld this "
        "turn. You may name the current topic once to hold the line, but do "
        "NOT explain the concept and do NOT quote or restate any formula."
    )
    return "\n".join(lines)


def scoped_session_note(context: dict[str, Any]) -> str:
    """[SESSION_CONTEXT] variant for scope-holding turns.

    Keeps class/subject/chapter/topic so the tutor knows the anchor, but drops
    the "teach helpfully / offer to return" tail so it does not double up with
    the redirect strategy already coming from the tutor turn directive.
    """
    class_label = context.get("classLabel") or context.get("classId") or "Class 10"
    subject = context.get("subjectName") or context.get("subjectId") or "Mathematics"
    chapter = context.get("chapterTitle") or context.get("chapterId") or "current chapter"
    topic = context.get("topicTitle") or context.get("topicId") or "current topic"

    return "\n".join(
        [
            f"{_SESSION_MARKER} Scope frame only — the student is trying to "
            "leave the current lesson. Do not open a general conversation.",
            f"- Class: {class_label}",
            f"- Subject: {subject}",
            f"- Chapter: {chapter}",
            f"- Topic: {topic}",
        ]
    )


def _upsert_marked_system_message(
    messages: list[dict[str, Any]],
    marker: str,
    content: str,
    *,
    pin_to_end: bool = False,
) -> None:
    """Replace the previous marked system note, or append if missing.

    ``pin_to_end`` moves the note after the newest turn instead of leaving it
    where it first landed. A per-turn directive has to be the last thing the
    model reads: kept up front it is outweighed by the conversation that
    follows it, and because its text changes every turn it also invalidates
    the cached prompt prefix for every message after it.
    """
    for index, message in enumerate(messages):
        if (
            isinstance(message, dict)
            and message.get("role") == "system"
            and isinstance(message.get("content"), str)
            and marker in message["content"]
        ):
            if pin_to_end:
                messages.pop(index)
                break
            messages[index] = {"role": "system", "content": content}
            return
    messages.append({"role": "system", "content": content})


def upsert_context_system_note(
    context: LLMContext,
    marker: str,
    content: str,
    *,
    pin_to_end: bool = False,
) -> None:
    """Write a marked system note into the live LLMContext (not a copy)."""
    messages = list(context.get_messages())
    _upsert_marked_system_message(messages, marker, content, pin_to_end=pin_to_end)
    context.set_messages(messages)


class SessionContextProcessor(FrameProcessor):
    """Consume `session_context`, `learning_context`, and `tutor_context` control messages."""

    def __init__(
        self,
        store: SessionContextStore,
        llm_context: LLMContext,
        *,
        session_id: str = "-",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_id = session_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputTransportMessageFrame):
            msg = frame.message
            if is_client_message(msg, CLIENT_SESSION_CONTEXT):
                raw = msg.get("context")
                if not isinstance(raw, dict):
                    logger.warning(
                        "[SessionContext] invalid payload | session={}",
                        self._session_id,
                    )
                    return

                cleaned = sanitize_client_dict(raw)
                self._store.set_context(cleaned)
                note = _system_note(cleaned)
                upsert_context_system_note(self._llm_context, _SESSION_MARKER, note)
                self._store.applied = True
                logger.info(
                    "[LEARNING_CONTEXT_RECEIVED] kind=session session={} topic={} chapter={} subject={}",
                    self._session_id,
                    raw.get("topicId"),
                    raw.get("chapterId"),
                    raw.get("subjectId"),
                )
                return

            if is_client_message(msg, CLIENT_LEARNING_CONTEXT):
                raw = msg.get("context")
                if not isinstance(raw, dict):
                    logger.warning(
                        "[LearningContext] invalid payload | session={}",
                        self._session_id,
                    )
                    return

                # Refuse accidental solution leakage from the student-visible payload.
                sanitized = sanitize_client_dict(
                    {
                        key: value
                        for key, value in raw.items()
                        if key
                        not in {
                            "solution",
                            "expectedAnswer",
                            "acceptedAnswers",
                            "hints",
                            "tutorOnly",
                        }
                    }
                )
                self._store.set_learning_context(sanitized)
                note = _learning_note(sanitized)
                upsert_context_system_note(self._llm_context, _LEARNING_MARKER, note)
                logger.info(
                    "[LEARNING_CONTEXT_RECEIVED] session={} topic={} section={} sectionTitle={} phase={} question={} hasVisible={}",
                    self._session_id,
                    sanitized.get("topicId"),
                    sanitized.get("sectionId"),
                    sanitized.get("sectionTitle"),
                    sanitized.get("phase"),
                    sanitized.get("questionId"),
                    bool((sanitized.get("visibleContent") or "").strip()),
                )
                return

            if is_client_message(msg, CLIENT_TUTOR_CONTEXT):
                raw = msg.get("context")
                if not isinstance(raw, dict):
                    logger.warning(
                        "[TutorContext] invalid payload | session={}",
                        self._session_id,
                    )
                    return
                trusted = verify_tutor_context(raw)
                if trusted is None:
                    logger.warning(
                        "[TutorContext] rejected unsigned or invalid payload | session={}",
                        self._session_id,
                    )
                    if tutor_context_signature_required():
                        return
                    trusted = sanitize_client_dict(
                        {key: value for key, value in raw.items() if key != "sig"}
                    )
                else:
                    trusted = sanitize_client_dict(trusted)
                # Tutor-only store — never inject solutions into a permanent system note.
                self._store.set_tutor_context(trusted)
                logger.info(
                    "[TutorContext] stored | session={} question={}",
                    self._session_id,
                    raw.get("questionId"),
                )
                return

        await self.push_frame(frame, direction)
