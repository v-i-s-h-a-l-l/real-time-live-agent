"""First-turn system note queued when a student connects.

Kept out of ``main.py`` so the greeting copy can be tested without starting
the WebSocket pipeline. Changing a string here changes what Lumina says
on join — keep tests in lockstep.
"""

from __future__ import annotations

from processors.session_context import SessionContextStore

_MATCH_LANGUAGE = (
    "After they speak, always match their language (English, Hindi, Tamil, or Telugu)."
)

# Qwen 3.6 on Groq refuses completions that have only system messages
# ("No user query found"). Seed the opening turn with a user line so the
# first spoken greeting can actually generate. That call also warms the
# model connection before the student's first real utterance.
OPENING_USER_SEED = "Hi"


def opening_system_message(session_store: SessionContextStore) -> str:
    """Spoken-style system instruction for the first LLM turn of a session."""
    topic = None
    section = None
    if session_store.context:
        topic = session_store.context.get("topicTitle") or session_store.context.get(
            "topicId"
        )
    if session_store.learning_context:
        section = session_store.learning_context.get(
            "sectionTitle"
        ) or session_store.learning_context.get("sectionId")
    if topic and section:
        return (
            f"The student just joined a Class 10 maths tutoring session. "
            f"The topic is '{topic}'. They are currently looking at the slide '{section}'. "
            "Greet them warmly in one short English sentence as Lumina, mention that slide, "
            "and invite a question. Keep it natural and brief — spoken, not a lecture. "
            f"{_MATCH_LANGUAGE}"
        )
    if topic:
        return (
            f"The student just joined a Class 10 maths tutoring session on '{topic}'. "
            "Greet them warmly in one short English sentence as Lumina, acknowledge the "
            "topic on screen, and invite them to ask about it or start with the current "
            "section. Keep it natural and brief — spoken, not a lecture. "
            f"{_MATCH_LANGUAGE}"
        )
    return (
        "The student just joined a Class 10 maths tutoring session. "
        "Greet them warmly in one short English sentence as Lumina and ask what "
        "they'd like to work on. Keep it natural and brief. "
        f"{_MATCH_LANGUAGE}"
    )


def opening_turn_messages(session_store: SessionContextStore) -> list[dict[str, str]]:
    """System instruction plus the user seed Groq/Qwen requires."""
    return [
        {"role": "system", "content": opening_system_message(session_store)},
        {"role": "user", "content": OPENING_USER_SEED},
    ]
