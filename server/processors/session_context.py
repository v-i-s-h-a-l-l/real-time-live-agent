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

_SESSION_MARKER = "[SESSION_CONTEXT]"
_LEARNING_MARKER = "[LEARNING_CONTEXT]"


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
            lines.append(f"- Visible content: {visible}")
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

                self._store.set_context(raw)
                note = _system_note(raw)
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
                sanitized = {
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
                # Tutor-only store — never inject solutions into a permanent system note.
                self._store.set_tutor_context(raw)
                logger.info(
                    "[TutorContext] stored | session={} question={}",
                    self._session_id,
                    raw.get("questionId"),
                )
                return

        await self.push_frame(frame, direction)
