"""FAQ teaching move — speak the grounded catalog answer, do not teach the slide.

Moved out of policy.py with no logic changes. Retrieval stays in tutor.faq.
"""

from __future__ import annotations

from tutor.faq import FAQEntry
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
)


def faq_decision(entry: FAQEntry) -> TutorDecision:
    return TutorDecision(
        intent=StudentIntent.FAQ,
        mode=TeachingMode.LEARN,
        move=ConversationMove.ANSWER_DIRECT,
        response_length=ResponseLength.SHORT,
        strategy=(
            "They asked a product FAQ, not a lesson question. Speak the FAQ "
            "answer in the student's language, teacher-like and concise. "
            "You may paraphrase, but do not add capabilities, subjects, "
            "classes, or tools that are not in the FAQ. Do not mention "
            "accounts, payments, banking, or customer support. Do not teach "
            "the current slide this turn."
        ),
        check_understanding=False,
        notes=("faq_knowledge",),
        faq_id=entry.id,
        faq_answer=entry.answer,
    )
