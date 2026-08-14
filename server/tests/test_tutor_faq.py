"""Product FAQ layer — grounded answers, no extra LLM, no lesson override."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from languages import LANG_EN, LANG_HI, LANG_TA, LANG_TE  # noqa: E402
from tutor.engine import TutorEngine  # noqa: E402
from tutor.faq import FAQS, FAQ_BY_ID, FAQ_KNOWLEDGE_MARKER, match_faq  # noqa: E402
from tutor.intent import detect_intent  # noqa: E402
from tutor.prompts import TUTOR_TURN_MARKER, build_tutor_turn_directive  # noqa: E402
from tutor.types import (  # noqa: E402
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorState,
)

#: Canonical question for each FAQ id — the ~15 product questions.
CANONICAL = (
    ("what_can_you_help", "What can you help me with?"),
    ("subjects", "Which subjects do you support?"),
    ("class_grade", "Which class/grade are you designed for?"),
    ("chapters_topics", "What chapters/topics can I learn?"),
    ("explain_concept", "Can you explain a concept?"),
    ("step_by_step", "Can you solve a problem step by step?"),
    ("hints_not_answers", "Can you give me hints instead of the answer?"),
    ("current_slide", "Can I ask questions about the current slide/content?"),
    ("practice", "Can I practice questions with you?"),
    ("explain_again", "Can you explain something again?"),
    ("interrupt", "Can I interrupt you while you're speaking?"),
    ("languages", "Can I talk to you in Hindi/Tamil/Telugu?"),
    ("type_instead", "Can I type instead of speaking?"),
    ("study_break", "Can I take a break while studying?"),
    ("dont_understand_question", "What should I do if I don't understand a question?"),
)

FORBIDDEN_CAPABILITIES = (
    "physics",
    "chemistry",
    "biology",
    "history",
    "geography",
    "class 9",
    "class 11",
    "class 12",
    "grade 9",
    "grade 11",
    "bank",
    "payment",
    "otp",
    "customer support",
    "988",
    "tele-manas",
    "geometry",
    "trigonometry",
    "calculus",
)

PARAPHRASES: dict[str, tuple[str, ...]] = {
    "what_can_you_help": (
        "How can you help me?",
        "What can you do?",
        "Can you help with homework?",
    ),
    "subjects": ("What subjects do you teach?", "Do you teach English?"),
    "class_grade": ("What class are you for?", "Which grade are you designed for?"),
    "chapters_topics": ("Which chapters can I learn?", "What topics do you cover?"),
    "explain_concept": ("Do you explain concepts?",),
    "step_by_step": ("Can you work through a problem step by step?",),
    "hints_not_answers": ("Do you give hints instead of the answer?",),
    "current_slide": ("Can I ask questions about the current slide?",),
    "practice": ("Can we practice?", "Do you have practice questions?"),
    "explain_again": ("Can you explain something again if I ask?",),
    "interrupt": ("Can I interrupt you?", "Can I barge in while you're speaking?"),
    "languages": (
        "Can I talk to you in Hindi?",
        "Can I speak in Tamil?",
        "हिंदी में बात कर सकते हो?",
    ),
    "type_instead": ("Can I type instead of speaking?", "Can I type my question?"),
    "study_break": ("Do you have study breaks?", "Can I pause while studying?"),
    "dont_understand_question": ("What should I do if I don't understand?",),
}

LESSON_NOT_FAQ = (
    "Can you help me with this equation?",
    "Explain this concept.",
    "Explain this.",
    "Can you explain that again?",
    "Give me a hint.",
    "Solve this question.",
    "Walk me through this.",
    "What is a quadratic equation?",
    "I don't understand.",
    "I don't understand this question.",
    "Wait, why did you use 5?",
    "Can you give me another question?",
    "Can you explain that second step?",
    "Who won the cricket match?",
)


def test_there_are_about_fifteen_faqs():
    assert len(FAQS) == 15
    assert len(CANONICAL) == 15
    assert {faq_id for faq_id, _ in CANONICAL} == {entry.id for entry in FAQS}


def test_canonical_questions_select_the_right_faq():
    for faq_id, question in CANONICAL:
        hit = match_faq(question)
        assert hit is not None, question
        assert hit.id == faq_id, (question, hit.id)
        assert hit.question == FAQ_BY_ID[faq_id].question
        assert hit.category in {
            "tutor_capability",
            "curriculum",
            "interaction",
            "language",
        }


def test_paraphrases_select_the_same_faq():
    for faq_id, phrases in PARAPHRASES.items():
        for phrase in phrases:
            hit = match_faq(phrase)
            assert hit is not None, phrase
            assert hit.id == faq_id, (phrase, hit.id if hit else None)


def test_engine_routes_all_canonical_faqs():
    engine = TutorEngine()
    for faq_id, question in CANONICAL:
        state = TutorState(
            phase="learning",
            topic_title="Euclid's Division Lemma",
            current_section_title="Euclid's Division Lemma",
        )
        decision = engine.decide(question, state)
        assert decision.intent == StudentIntent.FAQ, question
        assert decision.faq_id == faq_id, question
        assert decision.faq_answer == FAQ_BY_ID[faq_id].answer
        assert decision.mode == TeachingMode.LEARN
        assert decision.move == ConversationMove.ANSWER_DIRECT
        assert decision.response_length == ResponseLength.SHORT
        assert decision.check_understanding is False


def test_answers_do_not_hallucinate_capabilities():
    for entry in FAQS:
        text = entry.answer.lower()
        for phrase in FORBIDDEN_CAPABILITIES:
            assert phrase not in text, (entry.id, phrase)
        assert "math" in text or "class 10" in text or entry.category != "curriculum"


def test_curriculum_faqs_are_grounded_in_the_live_catalog():
    subjects = FAQ_BY_ID["subjects"].answer.lower()
    assert "mathematics" in subjects
    assert "english" in subjects
    assert "not available" in subjects
    chapters = FAQ_BY_ID["chapters_topics"].answer
    assert "Real Numbers" in chapters
    assert "Polynomials" in chapters
    assert "Pair of Linear Equations in Two Variables" in chapters
    assert "Quadratic Equations" in chapters
    grade = FAQ_BY_ID["class_grade"].answer
    assert "Class 10" in grade
    languages = FAQ_BY_ID["languages"].answer.lower()
    for name in ("hindi", "english", "tamil", "telugu"):
        assert name in languages
    brk = FAQ_BY_ID["study_break"].answer.lower()
    assert "one" in brk and "five" in brk


def test_lesson_questions_are_not_faqs():
    for utterance in LESSON_NOT_FAQ:
        assert match_faq(utterance) is None, utterance


def test_lesson_questions_keep_existing_tutoring_intents():
    engine = TutorEngine()
    cases = (
        ("Can you help me with this equation?", "learning", None),  # tutoring, not FAQ
        ("Explain this concept.", "learning", StudentIntent.EXPLANATION),
        ("Can you explain that again?", "learning", StudentIntent.REPEAT),
        ("Give me a hint.", "practice", StudentIntent.HINT),
        ("Solve this question.", "practice", StudentIntent.PRACTICE_REQUEST),
        ("I don't understand.", "learning", StudentIntent.CONFUSION),
        ("Wait, why did you use 5?", "learning", StudentIntent.WHY_HOW),
        ("Can you give me another question?", "learning", StudentIntent.PRACTICE_REQUEST),
        ("Who won the cricket match?", "learning", StudentIntent.UNRELATED),
        ("What is a quadratic equation?", "learning", StudentIntent.EXPLANATION),
    )
    for utterance, phase, intent in cases:
        state = TutorState(
            phase=phase,
            current_question_id="q1" if phase == "practice" else None,
            topic_title="Quadratic Formula",
        )
        decision = engine.decide(utterance, state)
        assert decision.intent != StudentIntent.FAQ, utterance
        if intent is not None:
            assert decision.intent == intent, f"{utterance!r} -> {decision.intent}"
        assert decision.faq_id is None


def test_homework_is_faq_but_this_equation_is_tutoring():
    engine = TutorEngine()
    homework = engine.decide("Can you help me with homework?", TutorState())
    assert homework.intent == StudentIntent.FAQ
    assert homework.faq_id == "what_can_you_help"
    lesson = engine.decide("Can you help me with this equation?", TutorState())
    assert lesson.intent != StudentIntent.FAQ
    assert lesson.faq_id is None


def test_faq_directive_keeps_active_language_and_omits_slide():
    engine = TutorEngine()
    state = TutorState(
        phase="learning",
        topic_title="Discriminant",
        current_section_title="Discriminant",
    )
    utterance = "Which subjects do you support?"
    decision = engine.decide(utterance, state)
    for lang, name in (
        (LANG_HI, "Hindi"),
        (LANG_TA, "Tamil"),
        (LANG_TE, "Telugu"),
        (LANG_EN, "English"),
    ):
        directive = build_tutor_turn_directive(
            decision=decision,
            state=state,
            learning_context={
                "phase": "learning",
                "sectionTitle": "Discriminant",
                "visibleContent": "The discriminant is b² − 4ac.",
            },
            tutor_context=None,
            utterance=utterance,
            active_language=lang,
        )
        assert TUTOR_TURN_MARKER in directive
        assert FAQ_KNOWLEDGE_MARKER in directive
        assert "Class 10 Mathematics" in directive
        assert f"Reply language: {name}" in directive
        assert "Visible content:" not in directive
        assert "b² − 4ac" not in directive
        assert "Do not invent extra capabilities" in directive


def test_faq_does_not_reset_interruption_recovery_path():
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_title="Discriminant")
    decision = engine.decide("Wait, why did you use 5?", state)
    assert decision.intent == StudentIntent.WHY_HOW
    assert "interruption_recovery" in decision.notes
    assert detect_intent("Wait, why did you use 5?") == StudentIntent.WHY_HOW


def test_faq_match_adds_no_noticeable_latency():
    samples = [q for _, q in CANONICAL] + list(LESSON_NOT_FAQ)
    started = time.perf_counter()
    for _ in range(40):
        for sample in samples:
            match_faq(sample)
    elapsed_ms = (time.perf_counter() - started) * 1000
    # ~1000 regex scans; ordinary tutoring is a single hint miss.
    assert elapsed_ms < 250, elapsed_ms


def test_voice_pipeline_does_not_insert_an_faq_processor():
    source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assembled = source.split("pipeline = Pipeline", 1)[1]
    assert "faq" not in assembled.lower()
    assert assembled.index("study_break") < assembled.index("tutor_turn")
    assert "incidental_gate" in assembled
    assert "allow_interruptions=True" in source


def test_asking_to_explain_in_hindi_stays_tutoring():
    """Language-of-explanation is not the 'can I speak Hindi?' FAQ."""
    utterance = "Explain Euclid's division lemma in Hindi."
    assert match_faq(utterance) is None
    engine = TutorEngine()
    decision = engine.decide(utterance, TutorState(phase="learning"))
    assert decision.intent != StudentIntent.FAQ
    assert decision.faq_id is None


def test_study_break_still_owns_an_actual_break_request():
    from tutor.breaks import BreakKind, BreakPhase, classify_utterance

    assert classify_utterance("Can I take a break?", BreakPhase.IDLE).kind == (
        BreakKind.REQUEST_NO_DURATION
    )
    # Capability wording is FAQ; starting a break stays the break layer.
    hit = match_faq("Do you have study breaks?")
    assert hit is not None
    assert hit.id == "study_break"
