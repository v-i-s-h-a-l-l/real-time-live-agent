"""Tutor Engine domain types — language-agnostic educational state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StudentIntent(str, Enum):
    EXPLANATION = "explanation"
    CLARIFICATION = "clarification"
    WHY_HOW = "why_how"
    REPEAT = "repeat"
    HINT = "hint"
    ANSWER_REQUEST = "answer_request"
    PRACTICE_REQUEST = "practice_request"
    STUDENT_ANSWER = "student_answer"
    CONFUSION = "confusion"
    DISAGREEMENT = "disagreement"
    ACKNOWLEDGEMENT = "acknowledgement"
    HESITATION = "hesitation"
    SUCCESS = "success"
    DEPTH_MORE = "depth_more"
    DEPTH_SHORT = "depth_short"
    DEPTH_SIMPLER = "depth_simpler"
    RELATED_EDUCATIONAL = "related_educational"
    TOPIC_CHANGE = "topic_change"
    UNRELATED = "unrelated"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class TeachingMode(str, Enum):
    LEARN = "learn"
    CLARIFY = "clarify"
    SOCRATIC = "socratic"
    HINT = "hint"
    PRACTICE = "practice"
    EVALUATE = "evaluate"
    CORRECT = "correct"
    REPEAT = "repeat"
    REDIRECT = "redirect"
    GREET = "greet"
    ACKNOWLEDGE = "acknowledge"


class ConversationMove(str, Enum):
    """What a human tutor would do next — not the spoken words."""

    ANSWER_DIRECT = "answer_direct"
    EXPLAIN = "explain"
    SIMPLIFY = "simplify"
    GIVE_EXAMPLE = "give_example"
    ANALOGY = "analogy"
    GUIDE = "guide"
    HINT = "hint"
    EVALUATE = "evaluate"
    CORRECT = "correct"
    ACKNOWLEDGE = "acknowledge"
    CELEBRATE = "celebrate"
    WAIT = "wait"
    REDIRECT = "redirect"
    REPEAT = "repeat"
    DEEPEN = "deepen"
    SHORTEN = "shorten"


class ResponseLength(str, Enum):
    MICRO = "micro"  # a beat: "Yeah." / "b is 5."
    SHORT = "short"  # 1–2 spoken sentences
    MEDIUM = "medium"  # 2–4 spoken sentences
    GUIDED = "guided"  # 1–2 sentences, at most one question


@dataclass
class TutorState:
    """Compact session teaching state — references content by ID, no curriculum dump."""

    class_id: str | None = None
    subject_id: str | None = None
    chapter_id: str | None = None
    topic_id: str | None = None
    topic_title: str | None = None
    phase: str = "learning"  # learning | practice | completed
    current_section_id: str | None = None
    current_section_title: str | None = None
    current_question_id: str | None = None
    hints_used: int = 0
    last_misconception: str | None = None
    teaching_mode: TeachingMode = TeachingMode.LEARN
    last_intent: StudentIntent = StudentIntent.UNKNOWN
    last_move: ConversationMove = ConversationMove.EXPLAIN
    confusion_streak: int = 0
    last_student_answer: str | None = None
    last_confusion_focus: str | None = None
    depth_preference: str = "normal"  # short | normal | deep | beginner
    off_topic_count: int = 0
    application_domain: str = "Class 10 Mathematics Tutor"
    subject: str = "Mathematics"

    def sync_from_learning_context(self, ctx: dict[str, Any] | None) -> None:
        if not ctx:
            return
        prev_question = self.current_question_id
        prev_section = self.current_section_id
        self.phase = str(ctx.get("phase") or self.phase)
        self.topic_id = _as_str(ctx.get("topicId")) or self.topic_id
        self.topic_title = _as_str(ctx.get("topicTitle")) or self.topic_title
        self.class_id = _as_str(ctx.get("classId")) or self.class_id
        self.subject_id = _as_str(ctx.get("subjectId")) or self.subject_id
        self.chapter_id = _as_str(ctx.get("chapterId")) or self.chapter_id
        self.current_section_id = _as_str(ctx.get("sectionId"))
        self.current_section_title = _as_str(ctx.get("sectionTitle"))
        self.current_question_id = _as_str(ctx.get("questionId"))
        if self.current_question_id != prev_question:
            self.hints_used = 0
            self.last_student_answer = None
            self.last_misconception = None
        if self.current_section_id != prev_section:
            self.confusion_streak = 0
            self.last_confusion_focus = None

    def sync_from_session_context(self, ctx: dict[str, Any] | None) -> None:
        if not ctx:
            return
        self.class_id = _as_str(ctx.get("classId")) or self.class_id
        self.subject_id = _as_str(ctx.get("subjectId")) or self.subject_id
        self.chapter_id = _as_str(ctx.get("chapterId")) or self.chapter_id
        self.topic_id = _as_str(ctx.get("topicId")) or self.topic_id
        self.topic_title = _as_str(ctx.get("topicTitle")) or self.topic_title


@dataclass(frozen=True)
class TutorDecision:
    intent: StudentIntent
    mode: TeachingMode
    strategy: str
    move: ConversationMove = ConversationMove.EXPLAIN
    response_length: ResponseLength = ResponseLength.SHORT
    allow_reveal_answer: bool = False
    use_next_hint: bool = False
    check_understanding: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)
    #: Deterministic verdict on a practice attempt (AnswerEvaluation value), if any.
    evaluation: str | None = None
    #: Hint ladder rung to use this turn: 0 = none, 4 = work it through together.
    hint_level: int = 0


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
