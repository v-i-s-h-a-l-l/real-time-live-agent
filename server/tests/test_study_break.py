"""Smart study breaks — structured state, duration rules, deterministic timer."""

from __future__ import annotations

import copy

from pathlib import Path

from processors.session_context import SessionContextStore
from tutor.breaks import (
    EVENT_BREAK_ENDED,
    EVENT_BREAK_STARTED,
    MAX_BREAK_MINUTES,
    MAX_BREAK_SECONDS,
    BreakKind,
    BreakPhase,
    BreakStore,
    classify_utterance,
    parse_duration,
    spoken_break_ended,
    spoken_break_started,
)
from tutor.types import TutorState


def _store() -> BreakStore:
    return BreakStore()


def test_want_a_break_asks_for_duration():
    store = _store()
    result = store.apply("I want a break.", 1_000.0)
    assert result is not None
    assert result.swallow
    assert store.state.phase == BreakPhase.REQUESTING_DURATION
    assert "how long" in result.spoken.lower()
    assert str(MAX_BREAK_MINUTES) in result.spoken.lower() or "five" in result.spoken.lower()
    assert result.schedule is False


def test_one_through_five_minute_starts():
    phrases = {
        1: "One minute.",
        2: "Two minutes.",
        3: "Three minutes.",
        4: "Four minutes.",
        5: "Five minutes.",
    }
    for minutes, phrase in phrases.items():
        store = _store()
        store.apply("Can I take a break?", 1_000.0)
        result = store.apply(phrase, 1_000.0)
        assert result is not None, phrase
        assert store.state.phase == BreakPhase.ACTIVE
        assert store.state.duration_minutes == minutes
        assert store.state.ends_at == 1_000.0 + minutes * 60
        assert result.event["type"] == EVENT_BREAK_STARTED
        assert result.event["durationMinutes"] == minutes
        assert result.event["startedAt"] == 1_000_000
        assert result.event["endsAt"] == int((1_000.0 + minutes * 60) * 1000)
        assert result.schedule is True
        assert spoken_break_started(minutes) == result.spoken


def test_direct_two_minute_request():
    store = _store()
    result = store.apply("I need a two-minute break.", 50.0)
    assert result is not None
    assert store.state.duration_minutes == 2
    assert store.state.started_at == 50.0
    assert store.state.ends_at == 170.0


def test_ten_minutes_is_not_silently_clamped():
    store = _store()
    result = store.apply("Give me 10 minutes.", 1.0)
    assert result is not None
    assert store.state.phase == BreakPhase.OFFERING_MAX
    assert store.state.active is False
    assert "five minutes" in result.spoken.lower()
    assert result.schedule is False
    yes = store.apply("Yes.", 1.0)
    assert yes is not None
    assert store.state.duration_minutes == MAX_BREAK_MINUTES


def test_thirty_minutes_and_half_hour_rejected():
    for phrase in ("Give me 30 minutes.", "Give me half an hour."):
        store = _store()
        result = store.apply(phrase, 1.0)
        assert result is not None, phrase
        assert store.state.phase == BreakPhase.OFFERING_MAX
        assert store.state.ends_at is None


def test_thirty_seconds_constrained_to_supported_minutes():
    store = _store()
    result = store.apply("I want a 30 second break.", 1.0)
    assert result is not None
    assert store.state.active is False
    assert "one to five" in result.spoken.lower()


def test_timer_uses_absolute_end_timestamp():
    store = _store()
    now = 1_700_000_000.0
    store.apply("Give me a 3 minute break.", now)
    remaining = store.state.remaining_seconds(now + 40)
    assert remaining == 140.0
    drifted = store.state.remaining_seconds(now + 40.7)
    assert abs(drifted - 139.3) < 1e-6


def test_break_end_fires_once():
    store = _store()
    store.apply("I need a two minute break.", 10.0)
    generation = store.generation
    first = store.expire(130.0, generation)
    second = store.expire(131.0, generation)
    third = store.expire(131.0, store.generation)
    assert first is not None
    assert first.event["type"] == EVENT_BREAK_ENDED
    assert first.spoken == spoken_break_ended(2)
    assert second is None
    assert third is None
    assert store.state.phase == BreakPhase.IDLE


def test_tts_completion_copy_matches_duration():
    assert "one-minute" in spoken_break_ended(1)
    assert "two-minute" in spoken_break_ended(2)
    assert "five-minute" in spoken_break_ended(5)
    assert "Break completed" not in spoken_break_ended(2)
    assert "I'll let you know" in spoken_break_started(2)


def test_im_back_cancels_remaining_time():
    store = _store()
    store.apply("I need a five minute break.", 0.0)
    result = store.apply("I'm back.", 30.0)
    assert result is not None
    assert store.state.phase == BreakPhase.IDLE
    assert result.cancel_timer is True
    assert result.schedule is False
    assert "welcome back" in result.spoken.lower()


def test_lets_continue_cancels_break():
    store = _store()
    store.apply("I need a two minute break.", 0.0)
    result = store.apply("Let's continue.", 15.0)
    assert result is not None
    assert store.state.phase == BreakPhase.IDLE
    assert "welcome back" in result.spoken.lower()


def test_changed_mind_and_continue_maths_end_break_immediately():
    for phrase in (
        "I changed my mind.",
        "I want to continue with maths.",
        "I want to continue.",
    ):
        store = _store()
        store.apply("I need a five minute break.", 0.0)
        result = store.apply(phrase, 20.0)
        assert result is not None, phrase
        assert store.state.phase == BreakPhase.IDLE, phrase
        assert "still on" not in result.spoken.lower(), phrase
        assert "left" not in result.spoken.lower(), phrase
        assert result.cancel_timer is True


def test_random_speech_during_break_does_not_resume():
    store = _store()
    store.apply("I need a three minute break.", 0.0)
    first = store.apply("Explain the question.", 10.0)
    second = store.apply("What's the answer?", 12.0)
    assert store.state.phase == BreakPhase.ACTIVE
    assert first is not None and first.swallow
    assert "still on your break" in first.spoken.lower()
    assert second is not None and second.swallow
    assert second.spoken == ""
    assert first.drop_last_user is True


def test_break_does_not_reset_lesson_or_question_or_context():
    learning = {
        "phase": "practice",
        "topicId": "zeros-coefficients",
        "sectionId": "rel-zeros",
        "sectionTitle": "Relationship Between Zeros and Coefficients",
        "questionId": "q3",
        "question": "Question 3",
        "visibleContent": "sum of zeros = -b/a",
    }
    session_store = SessionContextStore()
    session_store.set_learning_context(learning)
    session_store.set_context(
        {"topicId": "zeros-coefficients", "topicTitle": "Polynomials"}
    )
    tutor_state = TutorState(
        topic_id="zeros-coefficients",
        current_section_id="rel-zeros",
        current_question_id="q3",
        phase="practice",
        hints_used=2,
        confusion_streak=1,
    )
    before_learning = copy.deepcopy(session_store.learning_context)
    before_session = copy.deepcopy(session_store.context)
    before_tutor = copy.deepcopy(tutor_state)

    store = _store()
    store.apply("I want a break.", 0.0)
    store.apply("Two minutes.", 0.0)
    store.apply("Explain the question.", 5.0)
    store.apply("I'm back.", 20.0)

    assert session_store.learning_context == before_learning
    assert session_store.context == before_session
    assert tutor_state == before_tutor
    assert tutor_state.current_question_id == "q3"
    assert tutor_state.current_section_id == "rel-zeros"
    assert tutor_state.hints_used == 2


def test_reconnect_reset_invalidates_old_timer():
    store = _store()
    store.apply("I need a two minute break.", 0.0)
    stale = store.generation
    store.reset()
    assert store.expire(120.0, stale) is None
    assert store.state.phase == BreakPhase.IDLE


def test_second_break_request_does_not_stack_or_duplicate_timer():
    store = _store()
    first = store.apply("I need a two minute break.", 0.0)
    generation = store.generation
    ends_at = store.state.ends_at
    second = store.apply("I need a two minute break.", 20.0)
    assert first is not None and first.schedule is True
    assert second is not None
    assert second.schedule is False
    assert store.generation == generation
    assert store.state.ends_at == ends_at
    assert store.state.duration_minutes == 2
    assert "already on a break" in second.spoken.lower()


def test_cannot_extend_past_five_minutes_total():
    store = _store()
    store.apply("I need a two minute break.", 0.0)
    store.apply("Give me another five minutes.", 10.0)
    assert store.state.ends_at is not None
    assert store.state.ends_at <= MAX_BREAK_SECONDS
    assert store.state.duration_minutes <= MAX_BREAK_MINUTES


def test_break_it_down_is_not_a_study_break():
    assert classify_utterance("Can you break it down?", BreakPhase.IDLE).kind == BreakKind.NONE


def test_idle_one_minute_idiom_is_not_a_study_break():
    assert classify_utterance("Give me a minute.", BreakPhase.IDLE).kind == BreakKind.NONE
    assert classify_utterance("one minute", BreakPhase.IDLE).kind == BreakKind.NONE


def test_natural_variants():
    idle = BreakPhase.IDLE
    assert classify_utterance("I need a break", idle).kind == BreakKind.REQUEST_NO_DURATION
    assert classify_utterance("Can I take a break?", idle).kind == BreakKind.REQUEST_NO_DURATION
    assert classify_utterance("Give me a break", idle).kind == BreakKind.REQUEST_NO_DURATION
    assert classify_utterance("Let's take a break", idle).kind == BreakKind.REQUEST_NO_DURATION
    assert classify_utterance("I need two minutes", idle).kind == BreakKind.REQUEST_VALID
    assert classify_utterance("Can I have 3 minutes?", idle).kind == BreakKind.REQUEST_VALID
    assert classify_utterance("I want to rest for 5 minutes", idle).kind == BreakKind.REQUEST_VALID
    assert classify_utterance("Give me a 1 minute break", idle).kind == BreakKind.REQUEST_VALID


def test_hyphenated_two_minute_break():
    parsed = parse_duration("I need a two-minute break.")
    assert parsed is not None
    assert parsed.minutes == 2
    assert parsed.is_supported


def test_parse_duration_words_and_digits():
    assert parse_duration("two minutes").minutes == 2
    assert parse_duration("2 minutes").is_supported
    assert parse_duration("ten minutes").invalid_reason == "too_long"


def test_voice_pipeline_order_keeps_study_break_off_the_audio_path():
    source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assembled = source.split("pipeline = Pipeline", 1)[1]
    for name in (
        "audio_gate",
        "vad",
        "stt",
        "call_mute",
        "user_aggregator",
        "text_input",
        "study_break",
        "tutor_turn",
        "llm",
        "naturalizer",
        "tts",
    ):
        assert name in assembled, name
    assert assembled.index("stt") < assembled.index("study_break")
    assert assembled.index("user_aggregator") < assembled.index("study_break")
    assert assembled.index("study_break") < assembled.index("tutor_turn")
    assert assembled.index("study_break") < assembled.index("\n            llm,")


MATH_CONFIRM = (
    "So it can be represented as 255 equals 102 into 2 plus 51, am I right?"
)


def test_math_confirmation_is_not_a_break_request():
    idle = BreakPhase.IDLE
    asserting = BreakPhase.REQUESTING_DURATION
    assert classify_utterance(MATH_CONFIRM, idle).kind == BreakKind.NONE
    assert classify_utterance(MATH_CONFIRM, asserting).kind == BreakKind.NONE
    store = _store()
    store.apply("I want a break.", 0.0)
    assert store.state.phase == BreakPhase.REQUESTING_DURATION
    result = store.apply(MATH_CONFIRM, 1.0)
    assert result is None
    assert store.state.phase == BreakPhase.IDLE


def test_break_word_in_pushback_does_not_reask_duration():
    store = _store()
    first = store.apply("I want a break.", 0.0)
    assert first is not None
    canned = first.spoken
    for phrase in (
        "why are you asking me about a break",
        "I don't want to break",
        "I don't want a break",
        "what the fuck, why are you giving me break desperately",
    ):
        stuck = _store()
        stuck.apply("I want a break.", 0.0)
        result = stuck.apply(phrase, 1.0)
        assert result is None, phrase
        assert stuck.state.phase == BreakPhase.IDLE, phrase
        assert result is None or result.spoken != canned, phrase


def test_duration_ask_does_not_repeat_verbatim():
    store = _store()
    first = store.apply("I want a break.", 0.0)
    assert first is not None
    second = store.apply("I want a break.", 1.0)
    assert second is None
    assert store.state.phase == BreakPhase.REQUESTING_DURATION
    third = store.apply("Can I take a break?", 2.0)
    assert third is None
    assert store.state.phase == BreakPhase.IDLE


def test_two_minutes_still_works_after_how_long():
    store = _store()
    store.apply("I want a break.", 0.0)
    result = store.apply("Two minutes.", 1.0)
    assert result is not None
    assert store.state.phase == BreakPhase.ACTIVE
    assert store.state.duration_minutes == 2


def test_hostility_during_duration_ask_reaches_the_llm():
    from tutor.engine import TutorEngine

    store = _store()
    store.apply("I want a break.", 0.0)
    utterance = "what the fuck, why are you giving me break desperately"
    result = store.apply(utterance, 1.0)
    assert result is None
    assert store.state.phase == BreakPhase.IDLE
    decision = TutorEngine().decide(utterance, TutorState())
    assert "hostility_boundary" in decision.notes
