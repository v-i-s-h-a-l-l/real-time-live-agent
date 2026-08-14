"""Application-domain scope for the Class 10 Mathematics tutor.

The tutoring domain is a product rule, not a soft prompt suggestion.
Repeated insistence must never unlock general conversation.
"""

from __future__ import annotations

import re

from tutor.types import ConversationMove, StudentIntent, TeachingMode, TutorState

APPLICATION_DOMAIN = "Class 10 Mathematics Tutor"
APPLICATION_SUBJECT = "Mathematics"

ALLOWED_SCOPE = (
    "current lesson questions, related mathematics, educational context for the "
    "current concept, the current exercise, hints, explanations, examples, "
    "simplify/repeat requests, and natural acknowledgements"
)

FORBIDDEN_SCOPE = (
    "cricket, sports chat, politics, entertainment, news, shopping, weather, "
    "general trivia, unrelated personal questions, or any general-purpose conversation"
)

_SHORT_REFUSAL = re.compile(
    r"^\s*(no|nope|nah|no thanks|not really|i don'?t want to)\s*[.!?]?\s*$",
    re.I,
)

_RESUME_LESSON = re.compile(
    r"\b("
    r"(?:go |get )?back to (?:maths?|math|the lesson)|"
    r"let'?s (?:go back|get back|continue)|"
    r"continue with (?:the )?(?:maths?|math|lesson|examples)|"
    r"forget (?:cricket|that|it)|"
    r"never mind"
    r")\b",
    re.I,
)

_DOMAIN_INSIST = re.compile(
    r"\b("
    r"i want to talk|"
    r"now talk|"
    r"talk (?:to me )?(?:about )?(?:cricket|football|sports|politics|movies?|news)|"
    r"forget (?:the )?(?:maths?|math|lesson)|"
    r"don'?t (?:want to )?(?:do|talk(?: about)?) (?:maths?|math)|"
    r"no,?\s+(?:i want|talk|tell me)|"
    r"switch (?:to|into)"
    r")\b",
    re.I,
)

_ON_TOPIC_UNLOCK = {
    StudentIntent.EXPLANATION,
    StudentIntent.CLARIFICATION,
    StudentIntent.WHY_HOW,
    StudentIntent.REPEAT,
    StudentIntent.HINT,
    StudentIntent.ANSWER_REQUEST,
    StudentIntent.PRACTICE_REQUEST,
    StudentIntent.STUDENT_ANSWER,
    StudentIntent.CONFUSION,
    StudentIntent.DISAGREEMENT,
    StudentIntent.SUCCESS,
    StudentIntent.DEPTH_MORE,
    StudentIntent.DEPTH_SHORT,
    StudentIntent.DEPTH_SIMPLER,
    StudentIntent.RELATED_EDUCATIONAL,
    StudentIntent.FAQ,
}


def is_short_refusal(utterance: str) -> bool:
    return bool(_SHORT_REFUSAL.match((utterance or "").strip()))


def is_resume_lesson(utterance: str) -> bool:
    return bool(_RESUME_LESSON.search(utterance or ""))


def is_domain_insistence(utterance: str) -> bool:
    return bool(_DOMAIN_INSIST.search(utterance or ""))


def is_off_topic_lock(state: TutorState) -> bool:
    return (
        state.last_intent == StudentIntent.UNRELATED
        or state.last_move == ConversationMove.REDIRECT
        or state.teaching_mode == TeachingMode.REDIRECT
    )


def apply_domain_scope(
    intent: StudentIntent,
    utterance: str,
    state: TutorState,
) -> StudentIntent:
    """Keep the session inside Class 10 mathematics regardless of insistence.

    "No" never changes the application domain. After an off-topic turn it is
    treated as continued refusal to stay with maths, not as permission to
    become a general chatbot.
    """
    text = (utterance or "").strip()
    if not text:
        return intent

    if is_resume_lesson(text):
        return StudentIntent.EXPLANATION

    if intent == StudentIntent.UNRELATED:
        return StudentIntent.UNRELATED

    if intent == StudentIntent.RELATED_EDUCATIONAL:
        return intent

    locked = is_off_topic_lock(state)

    if locked and (is_short_refusal(text) or is_domain_insistence(text)):
        return StudentIntent.UNRELATED

    if locked and intent in _ON_TOPIC_UNLOCK and not is_domain_insistence(text):
        return intent

    if locked and intent in {
        StudentIntent.UNKNOWN,
        StudentIntent.GREETING,
        StudentIntent.HESITATION,
    }:
        return StudentIntent.UNRELATED

    if is_domain_insistence(text) and intent not in _ON_TOPIC_UNLOCK:
        return StudentIntent.UNRELATED

    return intent
