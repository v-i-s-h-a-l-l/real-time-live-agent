"""Conversational steering — choose an action, do not always continue the lesson."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.intent import detect_intent  # noqa: E402
from tutor.prompts import build_tutor_turn_directive  # noqa: E402
from tutor.steer import (  # noqa: E402
    PAUSE_GRANT_ACTIONS,
    SCOPE_HOLD_ACTIONS,
    STEER_NOTE_PREFIX,
    NeedKind,
    SteerAction,
    _ACTION_STRATEGY,
    _firmness_note,
    classify_need,
    is_pause_meta_talk,
    steering_strategy,
)
from tutor.types import (  # noqa: E402
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorState,
)

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


def _long(**kwargs) -> TutorState:
    return _state(session_started_at=time.monotonic() - 20 * 60, student_turns=10, **kwargs)


def _action(decision) -> str:
    for note in decision.notes:
        if note.startswith(STEER_NOTE_PREFIX):
            return note[len(STEER_NOTE_PREFIX) :]
    raise AssertionError(decision.notes)


def _action_or_none(decision) -> str | None:
    """Steer action if this was a steering turn, else None (a teaching turn)."""
    for note in decision.notes:
        if note.startswith(STEER_NOTE_PREFIX):
            return note[len(STEER_NOTE_PREFIX) :]
    return None


def _steer_decision(decision, action: SteerAction) -> None:
    low = decision.strategy.lower()
    assert decision.mode == TeachingMode.REDIRECT
    assert decision.move == ConversationMove.REDIRECT
    assert decision.response_length == ResponseLength.SHORT
    assert _action(decision) == action.value
    assert f"chosen action: {action.value}" in low
    assert "that's outside" not in low
    assert "second sentence continues" not in low
    assert "continue the current section" not in low
    assert (
        "do not tell them to go and also keep studying" in low
        or "do not teach" in low
        or "do not answer" in low
        or "do not grant a break" in low
        or "hook" in low
    )


def test_movie_just_started_defers_without_teaching():
    d = TutorEngine().decide("I want to watch a movie.", _state())
    assert detect_intent("I want to watch a movie.") == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.DEFER_LIGHT)
    assert "hook" in d.strategy.lower()
    assert "do not answer" in d.strategy.lower() or "do not grant a break" in d.strategy.lower()


def test_movie_after_long_session_still_redirects_with_a_hook():
    """Time served does not turn a movie ask into a granted break."""
    d = TutorEngine().decide("I want to watch a movie.", _long())
    _steer_decision(d, SteerAction.DEFER_LIGHT)
    low = d.strategy.lower()
    assert "hook" in low
    assert "do not grant a break" in low or "do not offer a break" in low


def test_eat_something_just_started_grants_pause():
    d = TutorEngine().decide("I want to eat something.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_hungry_just_started_grants_pause():
    d = TutorEngine().decide("I am hungry.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_iam_hungry_typo_is_still_hunger():
    assert detect_intent("iam hungry") == StudentIntent.UNRELATED
    d = TutorEngine().decide("iam hungry", _state())
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_hungry_after_working_grants_pause():
    d = TutorEngine().decide("I'm hungry.", _long())
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_hungry_mid_question_still_grants_the_pause():
    """A physical need is judged before the lesson, even mid-question."""
    d = TutorEngine().decide(
        "I'm hungry.",
        _state(phase="practice", current_question_id="q1"),
    )
    _steer_decision(d, SteerAction.GRANT_PAUSE)
    assert "concrete next step" in d.strategy.lower()


def test_stomach_growling_is_a_pause_need():
    d = TutorEngine().decide("My stomach is growling.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_tiredness_is_a_situation():
    d = TutorEngine().decide("I'm tired.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_brain_fried_unseen_phrasing():
    d = TutorEngine().decide("My brain is completely fried.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_stop_for_a_bit_is_a_pause():
    d = TutorEngine().decide("Can we take a break?", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_PAUSE)


def test_play_a_game_is_entertainment():
    d = TutorEngine().decide("I want to play a game.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.DEFER_LIGHT)


def test_boredom_changes_teaching_method_not_just_shortens():
    d = TutorEngine().decide("This is boring.", _state(phase="practice", current_question_id="q1"))
    assert d.intent == StudentIntent.DISENGAGEMENT
    # Boredom must change HOW we teach (example/analogy), not merely compress.
    assert d.mode == TeachingMode.CLARIFY
    assert d.move == ConversationMove.GIVE_EXAMPLE
    assert d.mode != TeachingMode.REDIRECT  # never leaves the topic
    low = d.strategy.lower()
    assert "example" in low or "analogy" in low
    assert "do not restate" in low or "do not just say the same thing" in low


def test_move_on_request_lets_them_shorten():
    d = TutorEngine().decide("Let's skip this, move on.", _state())
    assert d.intent == StudentIntent.DISENGAGEMENT
    assert d.move == ConversationMove.SHORTEN


def test_dont_want_to_study_is_disengagement():
    d = TutorEngine().decide("I don't feel like studying.", _state())
    assert d.intent == StudentIntent.DISENGAGEMENT
    assert d.mode != TeachingMode.REDIRECT


def test_capital_of_france_is_hold_scope():
    d = TutorEngine().decide("What's the capital of France?", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.HOLD_SCOPE)
    assert "do not answer" in d.strategy.lower()


def test_change_topic_defers_without_teaching():
    d = TutorEngine().decide("Can we talk about something else?", _state())
    assert d.intent in {StudentIntent.TOPIC_CHANGE, StudentIntent.UNRELATED}
    _steer_decision(d, SteerAction.DEFER_LIGHT)


def test_confused_is_teaching_not_steering():
    d = TutorEngine().decide("I don't understand this.", _state())
    assert d.intent == StudentIntent.CONFUSION
    assert d.mode == TeachingMode.CLARIFY
    assert d.move != ConversationMove.REDIRECT


def test_too_difficult_is_confusion():
    d = TutorEngine().decide("This is too difficult.", _state())
    assert d.intent == StudentIntent.CONFUSION
    assert d.mode == TeachingMode.CLARIFY


def test_explain_another_way_is_teaching():
    d = TutorEngine().decide("Can you explain it another way?", _state())
    assert d.intent in {StudentIntent.REPEAT, StudentIntent.EXPLANATION, StudentIntent.DEPTH_SIMPLER}
    assert d.move != ConversationMove.REDIRECT


def test_challenge_answer_is_disagreement():
    d = TutorEngine().decide("I think your answer is wrong.", _state())
    assert d.intent == StudentIntent.DISAGREEMENT
    assert d.mode == TeachingMode.CORRECT


def test_why_learn_this_is_teaching():
    d = TutorEngine().decide("Why do we need to learn this?", _state())
    assert d.intent in {StudentIntent.WHY_HOW, StudentIntent.RELATED_EDUCATIONAL}
    assert d.move != ConversationMove.REDIRECT


def test_joke_is_a_beat_not_a_lesson():
    d = TutorEngine().decide("Want to hear a joke?", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.JOKE_BEAT)


def test_genuine_leave_is_granted():
    d = TutorEngine().decide("I have to go.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.GRANT_LEAVE)


def test_earlier_confusion_is_available_not_invented():
    engine = TutorEngine()
    state = _state()
    engine.decide("I don't understand remainder.", state)
    d = engine.decide("I want to watch Netflix.", state)
    assert "remainder" in d.strategy.lower()
    assert "do not invent" in d.strategy.lower()
    directive = build_tutor_turn_directive(
        decision=d,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": TOPIC},
        tutor_context=None,
        utterance="I want to watch Netflix.",
    )
    assert "never invent earlier conversation" in directive.lower()
    assert "continue the current work" not in directive.lower()


def test_repeated_avoidance_becomes_a_check_in():
    engine = TutorEngine()
    state = _state(phase="practice", current_question_id="q1")
    first = engine.decide("I want to watch a movie.", state)
    second = engine.decide("My friends are calling.", state)
    third = engine.decide("I feel like playing something.", state)
    assert _action(first) == SteerAction.DEFER_LIGHT.value
    assert _action(second) == SteerAction.CHECK_IN.value
    assert _action(third) == SteerAction.HOLD_FIRM.value
    assert "confusing, boring, or hard" in second.strategy.lower()
    assert state.off_topic_count == 3
    assert state.consecutive_drift == 3


def test_unseen_off_topic_does_not_teach():
    d = TutorEngine().decide("Tell me about dinosaurs.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.DEFER_LIGHT)


def test_normal_maths_question_unchanged():
    d = TutorEngine().decide("What is Euclid's division lemma?", _state())
    assert d.intent == StudentIntent.EXPLANATION
    assert d.mode == TeachingMode.LEARN
    assert d.move != ConversationMove.REDIRECT


def test_movie_then_hunger_then_food_progresses():
    engine = TutorEngine()
    state = _state()
    movie = engine.decide("i wanna watch a movie", state)
    hungry = engine.decide("iam hungry", state)
    food = engine.decide("i want food", state)
    assert _action(movie) == SteerAction.DEFER_LIGHT.value
    assert _action(hungry) == SteerAction.GRANT_PAUSE.value
    assert _action(food) == SteerAction.CONFIRM_PAUSE.value
    assert "previous_need=pause" in food.strategy.lower() or "previous_action=grant_pause" in food.strategy.lower()
    assert food.strategy != hungry.strategy


def test_steer_directive_omits_slide_and_formulas():
    engine = TutorEngine()
    state = _state()
    decision = engine.decide("I'm hungry.", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context={
            "phase": "learning",
            "sectionTitle": TOPIC,
            "visibleContent": "Euclid's Division Lemma: a = bq + r with 0 ≤ r < b",
            "formulas": ["a = bq + r"],
        },
        tutor_context=None,
        utterance="I'm hungry.",
    )
    low = directive.lower()
    assert "visible content" not in low
    assert "formulas on screen" not in low
    assert "a = bq + r" not in low
    assert "teach out loud" not in low
    assert "current section on screen" not in low
    assert "do not quote the slide" in low or "omitted this turn" in low


def test_return_after_granted_pause_resumes():
    engine = TutorEngine()
    state = _state()
    engine.decide("I'm hungry.", state)
    assert state.awaiting_return is True
    back = engine.decide("I'm back.", state)
    assert _action(back) == SteerAction.RESUME_LESSON.value
    assert back.mode == TeachingMode.LEARN
    assert "resume" in back.strategy.lower()
    assert state.awaiting_return is False


def test_who_is_cm_of_tamil_nadu_holds_scope():
    """Off-topic factual questions must not be answered — hold scope, name the topic."""
    d = TutorEngine().decide("Who is the CM of Tamil Nadu?", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.HOLD_SCOPE)
    low = d.strategy.lower()
    assert "do not answer" in low
    assert "may name the current topic" in low


def test_political_trivia_variants_hold_scope():
    for utterance in (
        "Who is the prime minister of India?",
        "Who is the president of America?",
        "Who is the governor of Karnataka?",
        "Chief minister of Kerala?",
    ):
        d = TutorEngine().decide(utterance, _state())
        assert d.intent == StudentIntent.UNRELATED, utterance
        assert _action(d) == SteerAction.HOLD_SCOPE.value, utterance


def test_deviate_the_topic_is_topic_change_not_answered():
    d = TutorEngine().decide("Deviate the topic.", _state())
    assert d.intent == StudentIntent.TOPIC_CHANGE
    assert d.mode == TeachingMode.REDIRECT
    # Fresh session → light postponement; the strategy still refuses the pivot.
    assert _action(d) in {SteerAction.DEFER_LIGHT.value, SteerAction.HOLD_FIRM.value}


def test_topic_change_synonyms_all_route_to_redirect():
    for utterance in (
        "Change the topic.",
        "Switch the subject.",
        "Shift the topic.",
        "Let's talk about something else.",
        "Can we discuss something different?",
        "Different subject please.",
    ):
        d = TutorEngine().decide(utterance, _state())
        assert d.mode == TeachingMode.REDIRECT, utterance
        # Scope-holding, not a grant.
        assert _action(d) not in {
            SteerAction.GRANT_PAUSE.value,
            SteerAction.GRANT_LEAVE.value,
        }, utterance


def test_forget_maths_holds_scope():
    d = TutorEngine().decide("Forget maths, tell me about cricket.", _state())
    assert d.intent == StudentIntent.UNRELATED
    _steer_decision(d, SteerAction.HOLD_SCOPE)


def test_full_acceptance_sequence_stays_disciplined():
    """The exact sequence the user wants to pass end-to-end at policy level."""
    engine = TutorEngine()
    state = _state()

    hungry = engine.decide("I am hungry.", state)
    assert _action(hungry) == SteerAction.GRANT_PAUSE.value
    assert state.awaiting_return is True

    back = engine.decide("I am back.", state)
    assert _action(back) == SteerAction.RESUME_LESSON.value
    assert state.awaiting_return is False

    movie = engine.decide("I wanna watch a movie.", state)
    assert movie.intent == StudentIntent.UNRELATED
    # Wanting a movie is a want, not a rest need — it must never buy a pause.
    assert _action(movie) not in PAUSE_GRANT_ACTIONS
    assert state.awaiting_return is False
    # Scope-holding actions must allow the topic anchor to be named.
    assert "may name the current topic" in movie.strategy.lower()

    boring = engine.decide("This is boring.", state)
    # Boredom is NOT a topic change and NOT a break request — it must stay in
    # teaching and switch method.
    assert boring.intent == StudentIntent.DISENGAGEMENT
    assert boring.mode == TeachingMode.CLARIFY
    assert boring.move == ConversationMove.GIVE_EXAMPLE
    assert _action_or_none(boring) not in PAUSE_GRANT_ACTIONS
    assert state.awaiting_return is False

    deviate = engine.decide("Deviate the topic.", state)
    assert deviate.intent == StudentIntent.TOPIC_CHANGE
    assert deviate.mode == TeachingMode.REDIRECT
    # Boredom is a teaching turn, so consecutive drift resets. This is a
    # first tangent after they re-engaged — light redirect plus a hook.
    assert _action(deviate) == SteerAction.DEFER_LIGHT.value

    cm = engine.decide("Who is the CM of Tamil Nadu?", state)
    assert cm.intent == StudentIntent.UNRELATED
    # Still must not answer the fact. After repeated drift this is a check-in.
    assert _action(cm) in {SteerAction.HOLD_SCOPE.value, SteerAction.CHECK_IN.value}
    assert "do not answer the question" in cm.strategy.lower()

    why = engine.decide("Why does r have to be less than b?", state)
    assert why.intent == StudentIntent.WHY_HOW
    assert why.mode != TeachingMode.REDIRECT
    assert why.move == ConversationMove.ANSWER_DIRECT


def test_repeated_cm_question_gets_progressively_firmer_and_varied():
    """Same off-topic push twice → the second redirect must be firmer and not a repeat."""
    engine = TutorEngine()
    state = _state()
    first = engine.decide("Who is the CM of Tamil Nadu?", state)
    second = engine.decide("No, tell me the CM.", state)

    # Both hold the line, neither answers the question.
    assert first.mode == TeachingMode.REDIRECT
    assert second.mode == TeachingMode.REDIRECT
    assert _action(first) == SteerAction.HOLD_SCOPE.value
    assert _action(second) == SteerAction.CHECK_IN.value

    # The second reply must not answer and must not repeat the first redirect.
    assert first.strategy != second.strategy
    second_low = second.strategy.lower()
    assert "do not answer the question" in second_low
    assert "confusing, boring, or hard" in second_low


def test_first_deviation_instructs_variety_over_template():
    d = TutorEngine().decide("Who is the CM of Tamil Nadu?", _state())
    low = d.strategy.lower()
    # The strategy must tell the model to vary its wording and avoid a stock
    # template — while never quoting the template, which it would just copy.
    assert "template" in low
    assert "vary" in low or "fresh" in low
    assert "do not reuse its wording" in low
    assert "previous reply is in the conversation above" in low


_QUOTED_PHRASE = re.compile(r"['\u2018\u2019\u201c\u201d]\s*\w+(?:\s+\w+){2,}[\s.?!,]*['\u2018\u2019\u201c\u201d]")


def test_steering_prompts_quote_no_sample_sentences():
    """A quoted phrase in the prompt gets copied verbatim, ban or not.

    The fast models behind this tutor lift any quoted string straight into the
    reply and drop the surrounding negation, so "do NOT say 'we're still on the
    X slide'" is what produced that exact sentence on every single redirect.
    Describe the shape of the reply instead of ever quoting one.
    """
    offenders: list[str] = []

    for action, text in _ACTION_STRATEGY.items():
        if _QUOTED_PHRASE.search(text):
            offenders.append(f"_ACTION_STRATEGY[{action.value}]: {text}")

    for action in SCOPE_HOLD_ACTIONS:
        for consecutive in range(4):
            note = _firmness_note(action, consecutive)
            if _QUOTED_PHRASE.search(note):
                offenders.append(f"_firmness_note({action.value}, {consecutive}): {note}")

    for consecutive in range(4):
        _, strategy = steering_strategy(_state(), "I want to watch a movie.", consecutive=consecutive)
        if _QUOTED_PHRASE.search(strategy):
            offenders.append(f"steering_strategy(consecutive={consecutive}): {strategy}")

    assert not offenders, "quoted sample sentences get parroted:\n" + "\n".join(offenders)


def test_every_first_deviation_is_told_to_nod_then_hook():
    """A first redirect must hear them, refuse the tangent, and pull them back in.

    A fence-only line that only tells them to focus is the failure mode.
    """
    for utterance in (
        "i wanna watch a movie",
        "let's talk about cricket",
        "who is the CM of Tamil Nadu?",
        "can we change the topic",
        "i feel like playing a game",
    ):
        state = _state()
        d = TutorEngine().decide(utterance, state)
        low = d.strategy.lower()
        assert _action(d) not in PAUSE_GRANT_ACTIONS, utterance
        assert _action(d) != SteerAction.CHECK_IN.value, utterance
        assert "hook" in low, utterance
        assert "do not offer a break" in low, utterance
        assert "fence-only" in low, utterance


def test_second_deviation_checks_in_instead_of_fencing():
    engine = TutorEngine()
    state = _state()
    first = engine.decide("i wanna watch a movie", state)
    second = engine.decide("who is the CM of Tamil Nadu?", state)
    assert _action(first) == SteerAction.DEFER_LIGHT.value
    assert _action(second) == SteerAction.CHECK_IN.value
    low = second.strategy.lower()
    assert "confusing, boring, or hard" in low
    assert "do not answer the question" in low
    assert "mechanical" in low


def test_physical_need_prompts_a_concrete_next_step():
    d = TutorEngine().decide("I am hungry.", _state())
    low = d.strategy.lower()
    assert _action(d) == SteerAction.GRANT_PAUSE.value
    assert "concrete next step" in low
    assert "do not quiz" in low
    assert "message when they are back" in low


def test_tired_of_this_is_topic_frustration_not_a_break():
    d = TutorEngine().decide("I'm tired of this", _state())
    assert _action_or_none(d) != SteerAction.GRANT_PAUSE.value
    assert d.intent == StudentIntent.DISENGAGEMENT


def test_break_length_pushback_stays_in_pause_and_varies():
    engine = TutorEngine()
    state = _state()
    first = engine.decide("I need a break.", state)
    assert _action(first) == SteerAction.GRANT_PAUSE.value
    second = engine.decide("give me 5 hours", state)
    assert _action(second) == SteerAction.CONFIRM_PAUSE.value
    assert first.strategy != second.strategy
    low = second.strategy.lower()
    assert "new words" in low or "never repeat" in low
    assert "do not teach" in low


def test_hunger_idioms_are_read_as_a_real_need():
    """Students say they are hungry without using the word hungry."""
    for utterance in (
        "i wanna grab a quick bite",
        "let me grab a bite to eat",
        "i need to have lunch",
        "i'm thirsty, need some water",
        "i need to use the washroom",
        "i'm not feeling well",
        "i have a headache",
        "i'm feeling stressed",
    ):
        assert classify_need(utterance) == NeedKind.PAUSE, utterance


def test_hunger_after_a_refused_movie_still_gets_the_break():
    """A real need is judged on its own merits, not punished for a prior drift."""
    engine = TutorEngine()
    state = _state()
    movie = engine.decide("i wanna watch a movie", state)
    assert _action(movie) == SteerAction.DEFER_LIGHT.value

    bite = engine.decide("i wanna grab a quick bite", state)
    assert _action(bite) == SteerAction.GRANT_PAUSE.value
    assert state.awaiting_return is True


def test_entertainment_never_grants_a_pause_at_any_progress():
    """No amount of lesson progress turns "I want a movie" into a granted break.

    This was the regression: the fall-through tail granted a pause once the
    student had "worked" enough, so wanting entertainment bought a break.
    """
    situations = {
        "fresh": _state(),
        "long session": _long(),
        "after hints": _state(hints_used=2),
        "after confusion": _state(confusion_streak=1),
        "mid question": _state(phase="practice", current_question_id="q1"),
        "answered before": _state(last_student_answer="4"),
    }
    for label, state in situations.items():
        for utterance in (
            "I want to watch a movie.",
            "can we watch netflix instead",
            "I feel like playing a game.",
        ):
            d = TutorEngine().decide(utterance, state)
            action = _action(d)
            assert action not in PAUSE_GRANT_ACTIONS, f"{label}: {utterance!r} -> {action}"
            assert state.awaiting_return is False, label


def test_granted_hunger_break_does_not_spend_an_off_topic_strike():
    """A real need is not a dodge, so it must not make the next drift a repeat offence."""
    engine = TutorEngine()
    state = _state()
    engine.decide("I am hungry.", state)
    assert state.off_topic_count == 0

    engine.decide("I am back.", state)
    movie = engine.decide("I want to watch a movie.", state)
    # First actual attempt to leave → still the gentle end of the scale.
    assert _action(movie) == SteerAction.DEFER_LIGHT.value
    assert state.off_topic_count == 1


def test_boredom_is_not_treated_as_a_break_or_a_shorter_answer():
    """Boredom must change the teaching method, not shrink the same definition."""
    engine = TutorEngine()
    state = _state()
    d = engine.decide("i feel bored to learn this euclid and all", state)

    assert d.intent == StudentIntent.DISENGAGEMENT
    assert d.mode == TeachingMode.CLARIFY
    assert d.move == ConversationMove.GIVE_EXAMPLE
    # Room for an acknowledgement plus a real example, not a one-line summary.
    assert d.response_length == ResponseLength.MEDIUM
    # Never a break: boredom must not leave the tutor waiting for a return.
    assert _action_or_none(d) is None
    assert state.awaiting_return is False

    low = d.strategy.lower()
    assert "do not restate, compress, or re-word the definition" in low
    assert "brevity is not the fix" in low
    assert "boredom is not a break request" in low

    directive = build_tutor_turn_directive(
        decision=d,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": TOPIC},
        tutor_context=None,
        utterance="i feel bored to learn this euclid and all",
    ).lower()
    assert "change the teaching" in directive
    assert "do not offer to pause" in directive


def test_boredom_does_not_leave_a_standing_terseness_preference():
    engine = TutorEngine()
    state = _state()
    engine.decide("This is boring.", state)
    assert state.depth_preference != "short"

    # The next explanation must not be squeezed into a one-liner because they
    # were bored earlier.
    follow_up = engine.decide("Explain this concept.", state)
    assert "keep it short" not in " ".join(follow_up.notes).lower()


def test_outside_facts_stay_refused_however_often_they_are_asked():
    engine = TutorEngine()
    state = _state()
    expected = [
        SteerAction.HOLD_SCOPE.value,
        SteerAction.CHECK_IN.value,
        SteerAction.HOLD_FIRM.value,
        SteerAction.HOLD_FIRM.value,
    ]
    for utterance, action in zip(
        (
            "Who is the CM of Tamil Nadu?",
            "No, just tell me the CM.",
            "come on, who is the CM",
            "fine, who won the match then",
        ),
        expected,
        strict=True,
    ):
        d = engine.decide(utterance, state)
        assert _action(d) == action, utterance
        assert "do not answer the question" in d.strategy.lower(), utterance


def test_repeated_disengagement_stays_teaching_then_topic_change_firms():
    engine = TutorEngine()
    state = _state()
    first = engine.decide("I want a break.", state)
    second = engine.decide("I don't want to study.", state)
    third = engine.decide("Can we talk about something else?", state)
    assert _action(first) == SteerAction.GRANT_PAUSE.value
    assert second.intent == StudentIntent.DISENGAGEMENT
    assert third.intent in {StudentIntent.TOPIC_CHANGE, StudentIntent.UNRELATED}
    assert _action(third) in {
        SteerAction.DEFER_LIGHT.value,
        SteerAction.CHECK_IN.value,
        SteerAction.HOLD_FIRM.value,
    }


def test_why_did_you_give_me_a_break_is_not_a_new_pause():
    assert is_pause_meta_talk("why did you give me a break")
    assert classify_need("why did you give me a break") != NeedKind.PAUSE
    assert classify_need("I want a break.") == NeedKind.PAUSE

    engine = TutorEngine()
    state = _state()
    grant = engine.decide("I'm hungry.", state)
    assert _action(grant) == SteerAction.GRANT_PAUSE.value
    assert state.awaiting_return is True
    follow = engine.decide("why did you give me a break", state)
    assert _action_or_none(follow) != SteerAction.GRANT_PAUSE.value
    assert _action_or_none(follow) != SteerAction.CONFIRM_PAUSE.value
