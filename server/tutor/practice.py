"""Adaptive practice: answer evaluation, hint ladder, mastery and difficulty policy.

Pure, deterministic, dependency-free. No LLM calls, no I/O, no network — this runs
inline on the tutor turn and must stay microsecond-cheap so voice latency is unchanged.

The evaluator is the single source of truth for "did the student get it right?" for
both spoken and typed answers. The frontend mirrors `normalize_answer` /
`evaluate_answer` for instant practice-card feedback; the shared fixture in
`shared/practice-answer-cases.json` keeps the two implementations in lockstep.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnswerEvaluation(str, Enum):
    """How the tutor read the student's practice turn."""

    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    NEEDS_HINT = "needs_hint"  # "I don't know."
    HINT_REQUEST = "hint_request"  # "Can you give me a hint?"
    CONCEPTUAL_QUESTION = "conceptual_question"  # "Why do we use this formula?"
    AMBIGUOUS = "ambiguous"  # said something, but not an attempt we can score


class MasteryLevel(str, Enum):
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    DEVELOPING = "developing"
    STRONG = "strong"
    MASTERED = "mastered"


#: Curriculum labels ↔ the 1/2/3 scale used by the difficulty policy.
DIFFICULTY_BY_LABEL: dict[str, int] = {"easy": 1, "medium": 2, "hard": 3}
LABEL_BY_DIFFICULTY: dict[int, str] = {1: "easy", 2: "medium", 3: "hard"}

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 3

#: Level 0 = no help, 4 = work it through together.
MAX_HINT_LEVEL = 4


def difficulty_to_int(value: Any, default: int = MIN_DIFFICULTY) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, value))
    if isinstance(value, str):
        label = value.strip().lower()
        if label in DIFFICULTY_BY_LABEL:
            return DIFFICULTY_BY_LABEL[label]
        if label.isdigit():
            return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, int(label)))
    return default


def difficulty_to_label(value: int) -> str:
    return LABEL_BY_DIFFICULTY.get(max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, value)), "easy")


# --------------------------------------------------------------------------------------
# Response classification (is this even an answer?)
# --------------------------------------------------------------------------------------

_HINT_REQUEST = re.compile(
    r"\b(hint|clue|nudge|point me|give me (?:a |some )?help|help me (?:out|a bit)|thoda hint)\b",
    re.I,
)

_DONT_KNOW = re.compile(
    r"("
    r"\bi (?:really )?(?:don'?t|do not|dont) know\b"
    r"|\bno (?:idea|clue)\b"
    r"|\bnot sure(?: at all)?\b"
    r"|\bcan'?t (?:figure|work) (?:it|this) out\b"
    r"|\bi'?m stuck\b|\bi am stuck\b"
    r"|\bpata nahi\b"
    r")",
    re.I,
)

_CONCEPTUAL = re.compile(
    r"("
    r"\bwhy (?:do|does|is|are|would|should|can'?t)\b"
    r"|\bhow (?:come|does that|do we|does this) \b"
    r"|\bwhat (?:does|do) (?:that|this|it) mean\b"
    r"|\bwhere (?:does|did) (?:that|this|it) come from\b"
    r")",
    re.I,
)

#: Conversational padding students put in front of an actual answer.
_LEAD_IN = re.compile(
    r"^\s*(?:"
    r"i (?:think|guess|believe|got|reckon)(?: (?:it'?s|its|that|the answer is))?|"
    r"maybe|probably|i'?d say|umm+|uhh+|well|so|okay|ok|hmm+|"
    r"the answer (?:is|would be|should be)|answer(?: is|:)|"
    r"it(?:'s| is)|that(?:'s| is)|they(?:'re| are)|the (?:zeros?|roots?|values?) (?:are|is)"
    r")\b[\s,:-]*",
    re.I,
)

#: Trailing hedges — "…, but I'm not sure." should not turn a right answer into a shrug.
_TRAILING_HEDGE = re.compile(
    r"[\s,;.]*\b(?:but )?(?:i'?m|i am) not (?:really )?sure(?: about (?:it|that|this))?\s*[.!?]*\s*$",
    re.I,
)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?")

#: (x - 2)(x - 3) — a Class 10 student showing factored form rather than the roots.
_FACTOR_PAIR = re.compile(
    r"\(\s*[a-z]\s*([+-])\s*(\d+(?:\.\d+)?)\s*\)",
    re.I,
)

#: "so x = 3", "then the answer is 3" — the part that carries the final answer.
_FINAL_SEGMENT = re.compile(
    r"\b(?:so|then|therefore|hence|thus|which means|answer is|answer:)\b",
    re.I,
)

_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
        "for", "from", "get", "gets", "has", "have", "in", "into", "is", "it",
        "its", "of", "on", "or", "so", "than", "that", "the", "then", "there",
        "these", "they", "this", "to", "was", "we", "were", "will", "with",
    }
)


def normalize_quotes(value: str) -> str:
    """Curly quotes from typing and STT must not break "don't know" detection."""
    return (value or "").replace("\u2019", "'").replace("\u2018", "'")


def normalize_answer(value: str) -> str:
    """Canonical text form shared with the frontend practice card."""
    text = normalize_quotes(value).strip().lower()
    text = text.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u00d7", "*").replace("\u00f7", "/")
    text = text.replace("\u00b2", "^2").replace("\u00b3", "^3")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[.,;:!?]+$", "", text)
    return text.strip()


def strip_conversational_padding(value: str) -> str:
    """Drop lead-ins and trailing hedges so "I think 2 and 3" reads as "2 and 3"."""
    text = _TRAILING_HEDGE.sub("", normalize_quotes(value))
    previous = None
    while previous != text:
        previous = text
        text = _LEAD_IN.sub("", text, count=1)
    return text.strip(" ,:-")


def _parse_number(token: str) -> float | None:
    raw = token.replace(" ", "")
    try:
        if "/" in raw:
            numerator, _, denominator = raw.partition("/")
            denom = float(denominator)
            if denom == 0:
                return None
            return float(numerator) / denom
        return float(raw)
    except ValueError:
        return None


def _quantize(value: float) -> float:
    """Fold 0.5 and 1/2 onto the same key without dragging in float noise."""
    return round(value + 0.0, 6)


def extract_values(text: str) -> set[float]:
    """Numeric content of an answer, including roots implied by factored form."""
    cleaned = (text or "").replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    # Exponents are notation, not answer values: x^2 must not contribute a "2".
    cleaned = re.sub(r"(?:\^|\*\*)\s*-?\d+", " ", cleaned.replace("\u00b2", "^2").replace("\u00b3", "^3"))

    values: set[float] = set()
    for sign, magnitude in _FACTOR_PAIR.findall(cleaned):
        parsed = _parse_number(magnitude)
        if parsed is not None:
            values.add(_quantize(-parsed if sign == "+" else parsed))

    for token in _NUMBER.findall(cleaned):
        parsed = _parse_number(token)
        if parsed is not None:
            values.add(_quantize(parsed))
    return values


def _final_segment(text: str) -> str:
    """The tail of a step-by-step answer, where the final value usually lives."""
    matches = list(_FINAL_SEGMENT.finditer(text or ""))
    if not matches:
        return text or ""
    tail = text[matches[-1].end():].strip()
    return tail or (text or "")


def _content_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z]+|\d+(?:\.\d+)?", normalize_answer(text))
    return {token for token in tokens if token not in _STOP_WORDS}


def _token_overlap(student: str, candidate: str) -> float:
    student_tokens = _content_tokens(student)
    candidate_tokens = _content_tokens(candidate)
    if not candidate_tokens or not student_tokens:
        return 0.0
    shared = student_tokens & candidate_tokens
    return len(shared) / len(candidate_tokens)


@dataclass(frozen=True)
class EvaluationResult:
    evaluation: AnswerEvaluation
    #: Short, tutor-only reason — feeds the LLM directive, never spoken verbatim.
    reason: str = ""
    #: Values the student stated but the expected answer does not contain.
    missing_values: tuple[float, ...] = ()

    @property
    def is_attempt(self) -> bool:
        return self.evaluation in _ATTEMPT_EVALUATIONS


_ATTEMPT_EVALUATIONS = frozenset(
    {
        AnswerEvaluation.CORRECT,
        AnswerEvaluation.PARTIALLY_CORRECT,
        AnswerEvaluation.INCORRECT,
    }
)


def classify_practice_response(utterance: str) -> AnswerEvaluation | None:
    """Non-answer practice turns. Returns None when this looks like a real attempt."""
    raw = normalize_quotes(utterance).strip()
    if not raw:
        return AnswerEvaluation.AMBIGUOUS
    # "…, but I'm not sure." is a hedge on an answer; "I'm not sure." on its own is not.
    text = _TRAILING_HEDGE.sub("", raw).strip() or raw
    if _HINT_REQUEST.search(text):
        return AnswerEvaluation.HINT_REQUEST
    if _DONT_KNOW.search(text):
        return AnswerEvaluation.NEEDS_HINT
    if _CONCEPTUAL.search(text):
        return AnswerEvaluation.CONCEPTUAL_QUESTION
    return None


def evaluate_answer(
    utterance: str,
    expected_answer: str | None,
    accepted_answers: Iterable[str] | None = None,
) -> EvaluationResult:
    """Score a practice attempt without exact string matching.

    Order matters: explicit hint / don't-know / conceptual turns are never scored as
    wrong answers, and numeric equivalence beats literal text equality.
    """
    non_answer = classify_practice_response(utterance)
    if non_answer is not None:
        return EvaluationResult(non_answer)

    student_raw = strip_conversational_padding(utterance)
    student_norm = normalize_answer(student_raw)
    if not student_norm:
        return EvaluationResult(AnswerEvaluation.AMBIGUOUS, "empty response")

    candidates = [c for c in [expected_answer or "", *(accepted_answers or [])] if str(c).strip()]
    if not candidates:
        # No structured answer for this question — let the LLM judge the attempt.
        return EvaluationResult(AnswerEvaluation.AMBIGUOUS, "no expected answer available")

    for candidate in candidates:
        if student_norm == normalize_answer(strip_conversational_padding(str(candidate))):
            return EvaluationResult(AnswerEvaluation.CORRECT, "exact match")

    student_values = extract_values(student_raw)
    final_values = extract_values(_final_segment(student_raw))

    best_partial: EvaluationResult | None = None
    for candidate in candidates:
        expected_values = extract_values(str(candidate))
        if not expected_values:
            continue

        for values in (final_values, student_values):
            if not values:
                continue
            if values == expected_values:
                return EvaluationResult(AnswerEvaluation.CORRECT, "numeric match")
            if expected_values <= values and len(values) <= len(expected_values) + 3:
                # They showed working and landed on every required value.
                return EvaluationResult(AnswerEvaluation.CORRECT, "answer stated with working")
            if values < expected_values:
                missing = tuple(sorted(expected_values - values))
                best_partial = EvaluationResult(
                    AnswerEvaluation.PARTIALLY_CORRECT,
                    "part of the answer is missing",
                    missing,
                )

    if best_partial is not None:
        return best_partial

    for candidate in candidates:
        if extract_values(str(candidate)):
            continue
        overlap = _token_overlap(student_raw, str(candidate))
        if overlap >= 0.7:
            return EvaluationResult(AnswerEvaluation.CORRECT, "wording match")
        if overlap >= 0.4:
            return EvaluationResult(AnswerEvaluation.PARTIALLY_CORRECT, "partial wording match")

    if not student_values and len(student_norm.split()) <= 2:
        return EvaluationResult(AnswerEvaluation.AMBIGUOUS, "not an interpretable attempt")

    return EvaluationResult(AnswerEvaluation.INCORRECT, "does not match the expected answer")


# --------------------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionAttempt:
    question_id: str
    topic_id: str | None
    response: str
    evaluation: AnswerEvaluation
    attempt_number: int
    hints_used: int
    difficulty: int
    at: float


@dataclass
class QuestionProgress:
    """Per-question counters — reset when the student moves to a new question."""

    question_id: str
    difficulty: int = MIN_DIFFICULTY
    attempts: int = 0
    failed_attempts: int = 0
    hints_taken: int = 0
    solved: bool = False
    solved_unaided: bool = False

    @property
    def hint_level(self) -> int:
        """0 = no help yet, 4 = work the whole thing through together."""
        return min(MAX_HINT_LEVEL, self.hints_taken + self.failed_attempts)


@dataclass
class TopicProgress:
    """Lightweight per-topic signals. Session-scoped; shaped for later persistence."""

    topic_id: str
    correct: int = 0
    partial: int = 0
    incorrect: int = 0
    hints_used: int = 0
    retries: int = 0
    consecutive_correct: int = 0
    consecutive_incorrect: int = 0
    current_difficulty: int = MIN_DIFFICULTY
    questions_attempted: set[str] = field(default_factory=set)
    questions_solved: set[str] = field(default_factory=set)
    questions_solved_unaided: set[str] = field(default_factory=set)

    @property
    def total_attempts(self) -> int:
        return self.correct + self.partial + self.incorrect

    @property
    def accuracy(self) -> float:
        total = self.total_attempts
        return self.correct / total if total else 0.0

    @property
    def mastery(self) -> MasteryLevel:
        """Deliberately coarse — an honest estimate, not a fake percentage."""
        if self.total_attempts == 0:
            return MasteryLevel.NOT_STARTED
        solved = len(self.questions_solved)
        unaided = len(self.questions_solved_unaided)
        if (
            unaided >= 3
            and self.current_difficulty >= MAX_DIFFICULTY
            and self.consecutive_incorrect == 0
            and self.accuracy >= 0.75
        ):
            return MasteryLevel.MASTERED
        if solved >= 3 and self.accuracy >= 0.6 and self.consecutive_incorrect == 0:
            return MasteryLevel.STRONG
        if solved >= 1 and self.accuracy >= 0.35:
            return MasteryLevel.DEVELOPING
        return MasteryLevel.LEARNING

    @property
    def needs_help(self) -> bool:
        return self.consecutive_incorrect >= 2 or (
            self.total_attempts >= 3 and self.accuracy < 0.35
        )


def recommend_difficulty(topic: TopicProgress, question: QuestionProgress | None) -> int:
    """One bounded step per question. Never overreacts to a single slip."""
    current = topic.current_difficulty
    if question is None:
        return current
    if question.solved:
        # Clean first-attempt solve is the only thing that earns a step up.
        if question.solved_unaided:
            return min(MAX_DIFFICULTY, current + 1)
        return current
    if question.failed_attempts >= 2 or topic.consecutive_incorrect >= 2:
        return max(MIN_DIFFICULTY, current - 1)
    if question.failed_attempts >= 1 and question.hints_taken >= 2:
        return max(MIN_DIFFICULTY, current - 1)
    return current


@dataclass
class PracticeSnapshot:
    """Flat view handed to the prompt builder and the UI. No behaviour."""

    topic_id: str | None
    question_id: str | None
    evaluation: AnswerEvaluation | None
    attempt_number: int
    hints_used: int
    hint_level: int
    difficulty: int
    recommended_difficulty: int
    correct: int
    partial: int
    incorrect: int
    consecutive_correct: int
    consecutive_incorrect: int
    mastery: MasteryLevel
    reveal_solution: bool
    missing_values: tuple[float, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "topicId": self.topic_id,
            "questionId": self.question_id,
            "evaluation": self.evaluation.value if self.evaluation else None,
            "attemptNumber": self.attempt_number,
            "hintsUsed": self.hints_used,
            "hintLevel": self.hint_level,
            "difficulty": difficulty_to_label(self.difficulty),
            "recommendedDifficulty": difficulty_to_label(self.recommended_difficulty),
            "correct": self.correct,
            "partial": self.partial,
            "incorrect": self.incorrect,
            "consecutiveCorrect": self.consecutive_correct,
            "consecutiveIncorrect": self.consecutive_incorrect,
            "mastery": self.mastery.value,
            "revealSolution": self.reveal_solution,
        }


class PracticeTracker:
    """Per-connection adaptive practice state. Single source of truth for attempts."""

    def __init__(self, *, history_limit: int = 20) -> None:
        self._topics: dict[str, TopicProgress] = {}
        self._questions: dict[str, QuestionProgress] = {}
        self._recent: list[QuestionAttempt] = []
        self._history_limit = history_limit
        self._current_question_id: str | None = None
        self._current_topic_id: str | None = None
        self._last_evaluation: AnswerEvaluation | None = None
        self._last_missing: tuple[float, ...] = ()
        self._last_utterance: str | None = None

    # -- lifecycle ---------------------------------------------------------------

    def sync_question(
        self,
        question_id: str | None,
        *,
        topic_id: str | None,
        difficulty: Any = None,
    ) -> None:
        """Called every turn. Commits the difficulty step when the question changes."""
        if question_id == self._current_question_id:
            if topic_id:
                self._current_topic_id = topic_id
            return

        # Commit the difficulty step onto the topic the finished question belonged to.
        previous = self._questions.get(self._current_question_id or "")
        outgoing = self._topic()
        if outgoing is not None and previous is not None:
            outgoing.current_difficulty = recommend_difficulty(outgoing, previous)

        if topic_id:
            self._current_topic_id = topic_id
        topic = self._topic()
        self._current_question_id = question_id
        self._last_utterance = None
        self._last_evaluation = None
        self._last_missing = ()
        if question_id and question_id not in self._questions:
            resolved = difficulty_to_int(
                difficulty, default=topic.current_difficulty if topic else MIN_DIFFICULTY
            )
            self._questions[question_id] = QuestionProgress(
                question_id=question_id,
                difficulty=resolved,
            )
            if topic is not None and topic.total_attempts == 0:
                topic.current_difficulty = resolved

    def reset(self) -> None:
        self._topics.clear()
        self._questions.clear()
        self._recent.clear()
        self._current_question_id = None
        self._current_topic_id = None
        self._last_evaluation = None
        self._last_missing = ()
        self._last_utterance = None

    # -- recording ---------------------------------------------------------------

    def already_recorded(self, utterance: str) -> bool:
        """One student turn can reach the engine as more than one LLM frame."""
        return self._last_utterance is not None and self._last_utterance == (
            utterance or ""
        ).strip()

    def record(self, result: EvaluationResult, utterance: str, *, now: float | None = None) -> None:
        """Fold one practice turn into session state. Pure bookkeeping, no I/O."""
        self._last_utterance = (utterance or "").strip()
        question = self._question()
        topic = self._topic(create=True)
        self._last_evaluation = result.evaluation
        self._last_missing = result.missing_values
        if question is None or topic is None:
            return

        evaluation = result.evaluation
        if evaluation in (AnswerEvaluation.HINT_REQUEST, AnswerEvaluation.NEEDS_HINT):
            question.hints_taken += 1
            topic.hints_used += 1
            return
        if evaluation in (AnswerEvaluation.CONCEPTUAL_QUESTION, AnswerEvaluation.AMBIGUOUS):
            return

        question.attempts += 1
        topic.questions_attempted.add(question.question_id)
        if question.attempts > 1:
            topic.retries += 1

        if evaluation == AnswerEvaluation.CORRECT:
            topic.correct += 1
            topic.consecutive_correct += 1
            topic.consecutive_incorrect = 0
            if not question.solved:
                question.solved = True
                topic.questions_solved.add(question.question_id)
                if question.attempts == 1 and question.hints_taken == 0:
                    question.solved_unaided = True
                    topic.questions_solved_unaided.add(question.question_id)
        elif evaluation == AnswerEvaluation.PARTIALLY_CORRECT:
            topic.partial += 1
            topic.consecutive_incorrect = 0
            question.failed_attempts += 1
        else:
            topic.incorrect += 1
            topic.consecutive_incorrect += 1
            topic.consecutive_correct = 0
            question.failed_attempts += 1

        self._recent.append(
            QuestionAttempt(
                question_id=question.question_id,
                topic_id=topic.topic_id,
                response=(utterance or "").strip()[:200],
                evaluation=evaluation,
                attempt_number=question.attempts,
                hints_used=question.hints_taken,
                difficulty=question.difficulty,
                at=now if now is not None else time.time(),
            )
        )
        if len(self._recent) > self._history_limit:
            del self._recent[: len(self._recent) - self._history_limit]

    def clear_turn(self) -> None:
        """This turn was not a scored practice move (question, aside, off-topic)."""
        self._last_evaluation = None
        self._last_missing = ()

    def note_hint_taken(self) -> None:
        """An explicit hint turn that did not come through `record`."""
        question = self._question()
        topic = self._topic(create=True)
        if question is not None:
            question.hints_taken += 1
        if topic is not None:
            topic.hints_used += 1

    # -- reads -------------------------------------------------------------------

    @property
    def recent_attempts(self) -> tuple[QuestionAttempt, ...]:
        return tuple(self._recent)

    def topic_progress(self, topic_id: str | None = None) -> TopicProgress | None:
        return self._topics.get(topic_id or self._topic_key())

    def snapshot(self) -> PracticeSnapshot:
        question = self._question()
        topic = self._topic()
        difficulty = question.difficulty if question else (topic.current_difficulty if topic else MIN_DIFFICULTY)
        return PracticeSnapshot(
            topic_id=self._current_topic_id,
            question_id=self._current_question_id,
            evaluation=self._last_evaluation,
            attempt_number=question.attempts if question else 0,
            hints_used=question.hints_taken if question else 0,
            hint_level=question.hint_level if question else 0,
            difficulty=difficulty,
            recommended_difficulty=(
                recommend_difficulty(topic, question) if topic else difficulty
            ),
            correct=topic.correct if topic else 0,
            partial=topic.partial if topic else 0,
            incorrect=topic.incorrect if topic else 0,
            consecutive_correct=topic.consecutive_correct if topic else 0,
            consecutive_incorrect=topic.consecutive_incorrect if topic else 0,
            mastery=topic.mastery if topic else MasteryLevel.NOT_STARTED,
            reveal_solution=bool(question and question.hint_level >= MAX_HINT_LEVEL),
            missing_values=self._last_missing,
        )

    # -- internals ---------------------------------------------------------------

    def _question(self) -> QuestionProgress | None:
        if not self._current_question_id:
            return None
        return self._questions.get(self._current_question_id)

    def _topic_key(self) -> str:
        # Practice can start before the topic id arrives; keep one session bucket.
        return self._current_topic_id or "__session__"

    def _topic(self, *, create: bool = False) -> TopicProgress | None:
        key = self._topic_key()
        progress = self._topics.get(key)
        if progress is None and create:
            question = self._question()
            progress = TopicProgress(
                topic_id=key,
                current_difficulty=question.difficulty if question else MIN_DIFFICULTY,
            )
            self._topics[key] = progress
        return progress


def hint_for_level(hints: list[Any], level: int) -> str | None:
    """Map a ladder level onto the curriculum's hint list, clamped to what exists."""
    usable = [str(h).strip() for h in hints if str(h).strip()]
    if not usable or level <= 0:
        return None
    return usable[min(level - 1, len(usable) - 1)]
