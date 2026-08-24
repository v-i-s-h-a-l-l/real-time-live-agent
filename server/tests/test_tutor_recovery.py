"""Recovery follow-ups after a check-in or a failed re-engage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.intent import (  # noqa: E402
    CheckInReason,
    classify_check_in_reason,
    is_dismissive,
    is_hostile_to_tutor,
    is_missed_turn,
    is_ready_to_proceed,
)
from tutor.prompts import build_tutor_turn_directive  # noqa: E402
from tutor.steer import STEER_NOTE_PREFIX, SteerAction  # noqa: E402
from tutor.types import ConversationMove, TeachingMode, TutorState  # noqa: E402

TOPIC = "Euclid's Division Lemma"


def _state(**kwargs) -> TutorState:
    base = dict(
        phase="learning",
        topic_title=TOPIC,
        topic_id="euclid-lemma",
        current_section_title=TOPIC,
    )
    base.update(kwargs)
    return TutorState(**base)


def _action(decision) -> str | None:
    for note in decision.notes:
        if note.startswith(STEER_NOTE_PREFIX):
            return note[len(STEER_NOTE_PREFIX) :]
    return None


def _check_in_state() -> tuple[TutorEngine, TutorState]:
    engine = TutorEngine()
    state = _state()
    engine.decide("i wanna watch a movie", state)
    engine.decide("who is the CM of Tamil Nadu?", state)
    assert state.awaiting_reason is True
    return engine, state


def test_check_in_reason_classifier():
    assert classify_check_in_reason("boring") == CheckInReason.BORED
    assert classify_check_in_reason("it's confusing") == CheckInReason.CONFUSED
    assert classify_check_in_reason("hard to follow") == CheckInReason.CONFUSED
    assert classify_check_in_reason("yeah") == CheckInReason.UNCLEAR
    assert classify_check_in_reason("i wanna watch a movie") == CheckInReason.NONE


def test_dismissive_is_only_the_curt_pushback():
    assert is_dismissive("shutup")
    assert is_dismissive("shut up")
    assert is_dismissive("stop")
    assert is_dismissive("stop it")
    assert not is_dismissive("can we stop for a bit")
    assert not is_dismissive("I want to watch a movie")


def test_first_boredom_still_gives_an_example():
    d = TutorEngine().decide("This is boring.", _state())
    assert d.mode == TeachingMode.CLARIFY
    assert d.move == ConversationMove.GIVE_EXAMPLE


def test_after_check_in_boring_becomes_a_challenge_not_an_example():
    engine, state = _check_in_state()
    d = engine.decide("boring", state)
    assert d.move == ConversationMove.GUIDE
    assert d.mode == TeachingMode.SOCRATIC
    assert "active" in d.strategy.lower()
    assert "worked example" in d.strategy.lower()
    assert state.reengage_attempted is True
    assert state.awaiting_reason is False


def test_after_check_in_confusing_slows_down():
    engine, state = _check_in_state()
    d = engine.decide("it's confusing", state)
    assert d.move == ConversationMove.SIMPLIFY
    assert "slow down" in d.strategy.lower()
    assert "do not repeat the previous explanation" in d.strategy.lower()
    assert state.reengage_attempted is True


def test_after_check_in_hard_to_follow_slows_down():
    engine, state = _check_in_state()
    d = engine.decide("hard to follow", state)
    assert d.move == ConversationMove.SIMPLIFY


def test_unclear_check_in_answer_asks_which_reason():
    engine, state = _check_in_state()
    d = engine.decide("no good", state)
    assert "clarify_once" in d.notes
    assert "unclear" in d.strategy.lower()
    assert "do not change subject" in d.strategy.lower()
    assert state.awaiting_reason is True
    assert state.check_in_clarified is True


def test_after_reengage_shutup_asks_stop_or_didnt_click():
    engine = TutorEngine()
    state = _state()
    engine.decide("This is boring.", state)
    assert state.reengage_attempted is True
    d = engine.decide("shutup", state)
    assert _action(d) == SteerAction.CONFIRM_DONE.value
    low = d.strategy.lower()
    assert "stop the session" in low
    assert "did not click" in low
    assert state.awaiting_done_choice is True


def test_confirm_done_yes_lets_them_leave():
    engine = TutorEngine()
    state = _state()
    engine.decide("This is boring.", state)
    engine.decide("stop", state)
    d = engine.decide("yes", state)
    assert _action(d) == SteerAction.GRANT_LEAVE.value
    assert state.awaiting_return is True


def test_confirm_done_didnt_click_slows_down():
    engine = TutorEngine()
    state = _state()
    engine.decide("This is boring.", state)
    engine.decide("shutup", state)
    d = engine.decide("that last one didn't click", state)
    assert d.move == ConversationMove.SIMPLIFY
    assert state.awaiting_return is False


def test_hunger_then_later_turn_carries_physical_need_tone():
    engine = TutorEngine()
    state = _state()
    engine.decide("I am hungry.", state)
    engine.decide("I am back.", state)
    d = engine.decide("What is Euclid's division lemma?", state)
    assert "physical_need" in state.session_signals
    directive = build_tutor_turn_directive(
        decision=d,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": TOPIC},
        tutor_context=None,
        utterance="What is Euclid's division lemma?",
    ).lower()
    assert "physical_need" in directive
    assert "tone only" in directive


def test_movie_after_check_in_still_does_not_grant_a_pause():
    engine, state = _check_in_state()
    d = engine.decide("i wanna watch a movie", state)
    assert _action(d) != SteerAction.GRANT_PAUSE.value
    assert _action(d) != SteerAction.GRANT_LEAVE.value


def test_reason_switch_closes_the_loop_then_uses_the_new_approach():
    engine, state = _check_in_state()
    first = engine.decide("it's confusing", state)
    assert first.move == ConversationMove.SIMPLIFY
    assert state.last_recovery == "confused"
    assert state.awaiting_recovery_work is True

    d = engine.decide("actually it's boring", state)
    assert "loop_close" in d.notes
    assert d.move == ConversationMove.GUIDE
    low = d.strategy.lower()
    assert "close the loop" in low
    assert "do not wait" in low
    assert "active" in low
    assert "worked example" in low


def test_same_reason_before_the_task_does_not_add_a_loop_close():
    engine, state = _check_in_state()
    engine.decide("it's confusing", state)
    d = engine.decide("still confusing", state)
    assert "loop_close" not in d.notes


def test_answering_the_task_clears_the_unfinished_recovery():
    engine, state = _check_in_state()
    engine.decide("it's confusing", state)
    engine.decide("I get it now.", state)
    assert state.awaiting_recovery_work is False


def test_low_bandwidth_softens_the_next_teaching_turn():
    engine, state = _check_in_state()
    d = engine.decide("boring", state)
    assert "soft_tone" in d.notes
    directive = build_tutor_turn_directive(
        decision=d,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": TOPIC},
        tutor_context=None,
        utterance="boring",
    ).lower()
    assert "softer tone" in directive
    assert "do not mention earlier" in directive


def _practice_answer(
    engine: TutorEngine,
    state: TutorState,
    answer: str,
    *,
    question_id: str = "q1",
    expected: str = "4",
):
    return engine.decide(
        answer,
        state,
        learning_context={
            "phase": "practice",
            "questionId": question_id,
            "topicId": "euclid-lemma",
        },
        tutor_context={"expectedAnswer": expected, "acceptedAnswers": [expected]},
    )


def _wrong_practice_answer(engine: TutorEngine, state: TutorState) -> None:
    _practice_answer(engine, state, "99")


def test_correction_then_boredom_closes_the_correction_loop():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    assert state.just_corrected is True
    d = engine.decide("this is boring", state)
    assert "correction_close" in d.notes
    assert "soft_tone" in d.notes
    assert d.move == ConversationMove.SIMPLIFY
    low = d.strategy.lower()
    assert "one smaller sub-step" in low
    assert "normalizes getting a step wrong" in low
    assert "do not introduce a brand-new word-problem" in low
    assert "do not ask a fresh independent question" in low
    assert "active" not in low
    assert "hands-on" not in low


def test_correction_then_swearing_still_closes_then_continues():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("this is shit and boring", state)
    assert "correction_close" in d.notes
    low = d.strategy.lower()
    assert "one smaller sub-step" in low
    assert "do not combine" in low
    assert state.just_corrected is False


def test_correction_then_academic_question_skips_correction_close():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("Why does r have to be less than b?", state)
    assert "correction_close" not in d.notes


def test_first_boredom_without_a_correction_has_no_correction_close():
    d = TutorEngine().decide("This is boring.", _state())
    assert "correction_close" not in d.notes


def test_hunger_after_a_correction_still_grants_the_pause():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("I am hungry.", state)
    assert _action(d) == SteerAction.GRANT_PAUSE.value
    assert "correction_close" not in d.notes


def test_second_wrong_attempt_uses_struggle_pacing():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    first = _practice_answer(engine, state, "99")
    second = _practice_answer(engine, state, "98")
    assert "multi_struggle" not in first.notes
    assert "multi_struggle" in second.notes
    assert second.move == ConversationMove.SIMPLIFY
    assert second.response_length.value == "guided"
    low = second.strategy.lower()
    assert "first acknowledge" in low
    assert "same problem" in low
    assert "do not give a full worked example" in low
    assert "do not introduce a fresh independent task" in low
    assert state.struggle_pacing is True


def test_incomplete_then_wrong_on_same_question_counts_as_struggle():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _practice_answer(engine, state, "4", expected="4 and 5")
    d = _practice_answer(engine, state, "99", expected="4 and 5")
    assert "multi_struggle" in d.notes
    assert engine.practice.snapshot().consecutive_struggles == 2


def test_related_question_misses_also_count_as_consecutive_struggle():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _practice_answer(engine, state, "99", question_id="q1")
    state.current_question_id = "q2"
    d = _practice_answer(engine, state, "98", question_id="q2")
    assert "multi_struggle" in d.notes


def test_give_up_alone_triggers_struggle_pacing():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    d = _practice_answer(engine, state, "I don't know")
    assert "multi_struggle" in d.notes
    assert d.evaluation == "needs_hint"
    assert d.allow_reveal_answer is False
    assert "acknowledge the struggle" in d.strategy.lower()


def test_idk_plus_negative_language_still_uses_one_small_step():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    d = _practice_answer(engine, state, "idk this is stupid")
    assert "multi_struggle" in d.notes
    low = d.strategy.lower()
    assert "one smaller sub-step" in low
    assert "do not combine an example and a new task" in low


def test_boredom_during_struggle_does_not_launch_an_active_new_challenge():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _practice_answer(engine, state, "99")
    _practice_answer(engine, state, "98")
    d = engine.decide("this is boring", state)
    assert "multi_struggle" in d.notes
    assert "recovery_bored" not in d.notes
    assert "fresh independent task" in d.strategy.lower()


def test_correct_answer_clears_struggle_pacing():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _practice_answer(engine, state, "99")
    _practice_answer(engine, state, "98")
    assert state.struggle_pacing is True
    d = _practice_answer(engine, state, "4")
    assert d.evaluation == "correct"
    assert "multi_struggle" not in d.notes
    assert state.struggle_pacing is False


def test_hostility_classifier_targets_the_tutor_not_the_topic():
    assert is_hostile_to_tutor("shut up")
    assert is_hostile_to_tutor("shut the fuck up")
    assert is_hostile_to_tutor("stfu")
    assert is_hostile_to_tutor("fuck you")
    assert is_hostile_to_tutor("fuck off")
    assert is_hostile_to_tutor("you're stupid")
    assert is_hostile_to_tutor("you are such an idiot")
    assert is_hostile_to_tutor("you suck")
    assert is_hostile_to_tutor("stupid tutor")
    assert is_hostile_to_tutor("useless AI")
    assert not is_hostile_to_tutor("this is shit")
    assert not is_hostile_to_tutor("this is stupid")
    assert not is_hostile_to_tutor("i dont know")
    assert not is_hostile_to_tutor("boring")
    assert not is_hostile_to_tutor("what the fuck is this problem")
    assert is_hostile_to_tutor(
        "what the fuck, why are you giving me break desperately"
    )


def test_hostility_at_tutor_prepends_calm_boundary_line():
    engine = TutorEngine()
    state = _state()
    d = engine.decide("shut up you're useless", state)
    assert "hostility_boundary" in d.notes
    low = d.strategy.lower()
    assert "one short, calm, non-escalating boundary" in low
    assert "keep it respectful" in low
    assert "do not lecture" in low


def test_topic_frustration_does_not_trigger_hostility_boundary():
    engine = TutorEngine()
    state = _state()
    d = engine.decide("this is shit and boring", state)
    assert "hostility_boundary" not in d.notes


def test_hostility_during_a_break_still_addresses_the_request():
    engine = TutorEngine()
    state = _state()
    grant = engine.decide("I'm starving, can I grab a bite?", state)
    assert _action(grant) == SteerAction.GRANT_PAUSE.value
    followup = engine.decide("give me 5 hours you stupid bot", state)
    assert "hostility_boundary" in followup.notes
    assert _action(followup) == SteerAction.CONFIRM_PAUSE.value
    low = followup.strategy.lower()
    assert "never dodge" in low or "actual" in low
    assert "do not teach" in low


def test_correction_plus_frustration_never_launches_a_new_word_problem():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("this is shit and boring", state)
    low = d.strategy.lower()
    assert "one smaller sub-step" in low
    assert "do not introduce a brand-new word-problem" in low
    assert "do not ask a fresh independent question" in low
    assert "do not combine" in low
    assert "active" not in low
    assert "hands-on" not in low


def test_correction_plus_hostility_shows_both_signals():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("shut up, you're useless", state)
    assert "hostility_boundary" in d.notes
    assert "correction_close" in d.notes


def test_hunger_outranks_post_correction_frustration():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    d = engine.decide("I'm hungry, this is boring", state)
    assert _action(d) == SteerAction.GRANT_PAUSE.value
    assert "correction_close" not in d.notes
    assert "do not teach" in d.strategy.lower()


def test_correction_plus_frustration_fires_every_time_not_once():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    _wrong_practice_answer(engine, state)
    first = engine.decide("this is boring", state)
    assert "correction_close" in first.notes
    _wrong_practice_answer(engine, state)
    second = engine.decide("idk this sucks", state)
    assert "correction_close" in second.notes or "multi_struggle" in second.notes
    low = second.strategy.lower()
    assert "acknowledge" in low
    assert "one smaller" in low


def test_check_in_is_asked_only_once_per_episode():
    engine = TutorEngine()
    state = _state()
    engine.decide("i wanna watch a movie", state)
    check = engine.decide("who is the CM of Tamil Nadu?", state)
    assert _action(check) == SteerAction.CHECK_IN.value
    assert state.check_in_asked is True
    again = engine.decide("come on, cricket then", state)
    assert _action(again) == SteerAction.HOLD_FIRM.value
    assert state.check_in_asked is True


def test_ready_classifier_treats_go_ahead_as_engagement():
    assert is_ready_to_proceed("no questions lets get going")
    assert is_ready_to_proceed("lets start")
    assert is_ready_to_proceed("continue")
    assert is_ready_to_proceed("sure")
    assert is_ready_to_proceed("yes")
    assert is_ready_to_proceed("I'm ready")
    assert not is_ready_to_proceed("this is boring")
    assert not is_ready_to_proceed("who is the CM of Tamil Nadu?")
    assert is_missed_turn("why no reply")
    assert is_missed_turn("you didn't answer my question")
    assert not is_missed_turn("what is r")


def test_ready_after_a_drift_does_not_trigger_check_in():
    engine = TutorEngine()
    state = _state()
    engine.decide("i wanna watch a movie", state)
    d = engine.decide("no questions lets get going", state)
    assert _action(d) != SteerAction.CHECK_IN.value
    assert d.mode == TeachingMode.LEARN
    assert d.move != ConversationMove.REDIRECT
    assert "confusing, boring, or hard" not in d.strategy.lower()
    assert state.consecutive_drift == 0


def test_yes_after_check_in_continues_instead_of_diagnosing():
    engine, state = _check_in_state()
    d = engine.decide("yes", state)
    assert "ready_continue" in d.notes
    assert "clarify_once" not in d.notes
    assert _action(d) != SteerAction.CHECK_IN.value


def test_second_unclear_check_in_answer_proceeds():
    engine, state = _check_in_state()
    first = engine.decide("no good", state)
    assert "clarify_once" in first.notes
    second = engine.decide("whatever that means", state)
    assert "ready_continue" in second.notes
    assert "clarify_once" not in second.notes


def test_missed_turn_gets_a_gap_acknowledgment():
    engine = TutorEngine()
    state = _state()
    d = engine.decide("why no reply, what is Euclid's division lemma?", state)
    assert "gap_ack" in d.notes
    assert "skipped" in d.strategy.lower() or "gap" in d.strategy.lower()


def test_awaiting_reason_clears_after_turn_budget():
    engine, state = _check_in_state()
    assert state.awaiting_reason is True
    engine.decide("tell me about dinosaurs", state)
    assert state.awaiting_reason is True
    engine.decide("who won the IPL?", state)
    assert state.awaiting_reason is True
    engine.decide("what's the weather?", state)
    assert state.awaiting_reason is False
    assert state.check_in_asked is False
