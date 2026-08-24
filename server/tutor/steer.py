"""Choose what a tutor should *do* on an off-topic / situation turn.

No extra LLM. No per-phrase replies. Policy picks an action from lesson
state + recent steer memory; the main LLM only speaks that action.
"""

from __future__ import annotations

import re
import time
from enum import Enum

from tutor.types import TutorState

JUST_STARTED_MINUTES = 6.0
LONG_SESSION_MINUTES = 12.0
EARLY_TURN_LIMIT = 4
WORKED_TURN_LIMIT = 8

STEER_NOTE_PREFIX = "steer:"


class NeedKind(str, Enum):
    PAUSE = "pause"
    ENTERTAINMENT = "entertainment"
    TRIVIA = "trivia"
    JOKE = "joke"
    LEAVE = "leave"
    TOPIC = "topic"
    OTHER = "other"


class SteerAction(str, Enum):
    GRANT_PAUSE = "grant_pause"
    CONFIRM_PAUSE = "confirm_pause"
    FINISH_THEN_PAUSE = "finish_then_pause"
    DEFER_LIGHT = "defer_light"
    HOLD_FIRM = "hold_firm"
    HOLD_SCOPE = "hold_scope"
    CHECK_IN = "check_in"
    CONFIRM_DONE = "confirm_done"
    JOKE_BEAT = "joke_beat"
    GRANT_LEAVE = "grant_leave"
    RESUME_LESSON = "resume_lesson"


PAUSE_GRANT_ACTIONS = frozenset(
    {
        SteerAction.GRANT_PAUSE.value,
        SteerAction.CONFIRM_PAUSE.value,
        SteerAction.GRANT_LEAVE.value,
    }
)
# Scope-holding actions — the student is trying to leave the lesson and the
# tutor is holding the line. These escalate: light redirect → check-in → firm.
SCOPE_HOLD_ACTIONS = frozenset(
    {
        SteerAction.DEFER_LIGHT,
        SteerAction.FINISH_THEN_PAUSE,
        SteerAction.HOLD_FIRM,
        SteerAction.HOLD_SCOPE,
        SteerAction.CHECK_IN,
    }
)
DRIFT_NEEDS = frozenset(
    {
        NeedKind.ENTERTAINMENT,
        NeedKind.TRIVIA,
        NeedKind.JOKE,
        NeedKind.TOPIC,
        NeedKind.OTHER,
    }
)
SITUATION_NEEDS = frozenset(
    {
        NeedKind.PAUSE,
        NeedKind.ENTERTAINMENT,
        NeedKind.LEAVE,
        NeedKind.JOKE,
    }
)

# Coarse need kinds for action choice — not response templates.
_LEAVE = re.compile(
    r"\b("
    r"i (?:have to|need to|gotta|got to|should) (?:go|leave|run)|"
    r"i(?:'?ve)? (?:got to|gotta) (?:go|leave)|"
    r"i need to (?:head|get) (?:home|out)|"
    r"can i (?:leave|go home)"
    r")\b",
    re.I,
)

_PAUSE = re.compile(
    r"("
    r"\b(?:hungry|starving|exhausted|sleepy|drained|wiped|thirsty)\b|"
    r"\b(?:unwell|nauseous|dizzy|headache|migraine|stressed|anxious)\b|"
    r"\b(?:not|don'?t) feeling (?:well|good|ok|okay)\b|"
    r"\bfeeling (?:sick|ill|bad|stressed|anxious)\b|"
    r"\bi haven'?t eaten\b|"
    r"\b(?:eat|eating|snack|food)\b|"
    # "grab a bite", "quick bite", "bite to eat" — the most common way a student
    # says they are hungry without ever using the word.
    r"\b(?:bite|lunch|dinner|breakfast|nap)\b|"
    r"\b(?:washroom|bathroom|restroom|toilet|loo)\b|"
    r"\b(?:drink|get|need) (?:some )?water\b|"
    r"\b(?:medicine|meds)\b|"
    r"\bmy (?:stomach|tummy|belly|brain|head)\b|"
    r"\b(?:fried|growling)\b|"
    r"\b(?:tired|exhausted|sleepy)(?!\s+of)\b|"
    r"\b(?:break|pause|rest)\b|"
    r"\b(?:stop|pause) for a (?:bit|while|minute|sec)|"
    r"\bcan we (?:stop|pause|rest)\b"
    r")",
    re.I,
)

_ENTERTAINMENT = re.compile(
    r"\b("
    r"movie|film|netflix|youtube|song|"
    r"game|gaming|play(?:ing)?|"
    r"friends? (?:are|is) (?:calling|texting|waiting)"
    r")\b",
    re.I,
)

_TRIVIA = re.compile(
    r"("
    r"\b(?:cricket|football|soccer|tennis|ipl|dhoni|kohli|messi)\b|"
    r"\b(?:weather|forecast|capital of|who won)\b|"
    r"\b(?:politics|election|bitcoin|stock market)\b|"
    r"\b(?:prime minister|chief minister|cm of|pm of|president of|"
    r"governor of|mayor of|mla|cabinet minister)\b|"
    r"\bwho is the (?:cm|pm|president|governor|mayor|prime minister|chief minister)\b"
    r")",
    re.I,
)

_JOKE = re.compile(r"\bjoke\b", re.I)

_RETURN = re.compile(
    r"("
    r"\bi(?:'?m|\s+am)\s+back\b|"
    r"\bi(?:'?m|\s+am)\s+ready\b|"
    r"\bi\s+changed\s+my\s+mind\b|"
    r"\bi\s+want\s+to\s+continue\b|"
    r"\bwant\s+to\s+continue\s+with\s+(?:the\s+)?(?:maths?|math|lesson)\b|"
    r"\blet'?s\s+(?:continue|go\s+back|get\s+back|resume)\b|"
    r"\bready\s+to\s+(?:continue|go\s+back|resume)\b|"
    r"\bcontinue\s+with\s+(?:the\s+)?(?:maths?|math|lesson)\b"
    r")",
    re.I,
)

_BREAK_NEGOTIATE = re.compile(
    r"("
    r"\b\d+\s*(?:hour|hr|hrs|minute|min|mins|sec|seconds?)\b|"
    r"\b(?:an?|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|sixty)\s+"
    r"(?:hour|hr|minute|min)s?\b|"
    r"\b(?:longer|more time|too short|not enough time)\b|"
    r"\bgive me\s+\d+"
    r")",
    re.I,
)

# Talking about a pause that already happened — not a new rest request.
_PAUSE_META = re.compile(
    r"("
    r"\bwhy\s+did\s+you\s+(?:give|grant|offer)\s+(?:me\s+)?(?:a\s+)?(?:break|pause|rest)\b|"
    r"\byou\s+(?:gave|granted|offered)\s+me\s+a\s+(?:break|pause|rest)\b|"
    r"\bi\s+didn'?t\s+(?:even\s+)?(?:ask|want)\s+(?:for\s+)?(?:a\s+)?(?:break|pause|rest)\b|"
    r"\b(?:what|which)\s+(?:break|pause|rest)\b|"
    r"\bdon'?t\s+want\s+a\s+(?:break|pause|rest)\b|"
    r"\bwhy\s+a\s+(?:break|pause|rest)\b|"
    r"\bwhy\s+did\s+you\s+(?:stop|pause)\b"
    r")",
    re.I,
)

_TYPO_IAM = re.compile(r"\biam\b", re.I)


def soften_student_text(utterance: str) -> str:
    """Fix glued first-person typos so routing can see the utterance."""
    text = (utterance or "").strip()
    if not text:
        return ""
    return _TYPO_IAM.sub("i am", text)


def is_return_utterance(utterance: str) -> bool:
    return bool(_RETURN.search(soften_student_text(utterance)))


def is_break_negotiation(utterance: str) -> bool:
    """Pushback on break length after a pause was already on the table."""
    return bool(_BREAK_NEGOTIATE.search(soften_student_text(utterance)))


def is_pause_meta_talk(utterance: str) -> bool:
    """True when they are talking about a break, not asking for one."""
    return bool(_PAUSE_META.search(soften_student_text(utterance)))


def classify_need(utterance: str, *, topic_shift: bool = False) -> NeedKind:
    text = soften_student_text(utterance)
    if not text:
        return NeedKind.OTHER
    if _LEAVE.search(text):
        return NeedKind.LEAVE
    if is_pause_meta_talk(utterance):
        pass
    elif _PAUSE.search(text):
        return NeedKind.PAUSE
    if _JOKE.search(text):
        return NeedKind.JOKE
    if _TRIVIA.search(text):
        return NeedKind.TRIVIA
    if _ENTERTAINMENT.search(text):
        return NeedKind.ENTERTAINMENT
    if topic_shift:
        return NeedKind.TOPIC
    return NeedKind.OTHER


def session_minutes(state: TutorState, *, now: float | None = None) -> float | None:
    started = state.session_started_at
    if started is None:
        return None
    return max(0.0, (now if now is not None else time.monotonic()) - started) / 60.0


def _lesson_progress(state: TutorState, *, now: float | None = None) -> dict[str, object]:
    minutes = session_minutes(state, now=now)
    mid_task = bool(state.current_question_id) or state.phase == "practice"
    almost_done = state.phase == "completed"
    worked = bool(
        (minutes is not None and minutes >= LONG_SESSION_MINUTES)
        or state.student_turns >= WORKED_TURN_LIMIT
        or state.last_student_answer
        or state.hints_used > 0
        or state.confusion_streak > 0
    )
    early = (
        not mid_task
        and not almost_done
        and not worked
        and state.student_turns < EARLY_TURN_LIMIT
        and (minutes is None or minutes < JUST_STARTED_MINUTES)
    )
    return {
        "minutes": minutes,
        "mid_task": mid_task,
        "almost_done": almost_done,
        "worked": worked,
        "early": early,
    }


def _last_action(state: TutorState) -> SteerAction | None:
    raw = state.last_steer_action
    if not raw:
        return None
    try:
        return SteerAction(raw)
    except ValueError:
        return None


def choose_steer_action(
    state: TutorState,
    utterance: str,
    *,
    consecutive: int,
    topic_shift: bool = False,
    now: float | None = None,
) -> SteerAction:
    """Pick one tutor action using this utterance plus recent steer memory."""
    need = classify_need(utterance, topic_shift=topic_shift)
    last_action = _last_action(state)
    same_need = bool(state.last_need_kind and state.last_need_kind == need.value)

    # Priority 1: physical / emotional needs and break-length pushback.
    # Entertainment never enters here.
    if state.awaiting_return and not is_pause_meta_talk(utterance) and (
        need in {NeedKind.PAUSE, NeedKind.LEAVE} or is_break_negotiation(utterance)
    ):
        if need == NeedKind.LEAVE:
            return SteerAction.GRANT_LEAVE
        return SteerAction.CONFIRM_PAUSE

    if same_need and need in {NeedKind.PAUSE, NeedKind.LEAVE}:
        if last_action in {
            SteerAction.GRANT_PAUSE,
            SteerAction.CONFIRM_PAUSE,
            SteerAction.GRANT_LEAVE,
        }:
            return (
                SteerAction.GRANT_LEAVE
                if need == NeedKind.LEAVE
                else SteerAction.CONFIRM_PAUSE
            )

    if need == NeedKind.PAUSE:
        return SteerAction.GRANT_PAUSE
    if need == NeedKind.LEAVE:
        return SteerAction.GRANT_LEAVE

    # Two or more drifts in a row: diagnose once, then hold the line.
    # Never ask the confusing/boring/hard question twice in the same episode.
    if need in DRIFT_NEEDS or topic_shift:
        if state.check_in_asked and consecutive >= 1:
            return SteerAction.HOLD_FIRM
        if consecutive >= 3:
            return SteerAction.HOLD_FIRM
        if consecutive >= 1:
            return SteerAction.CHECK_IN
        if need == NeedKind.TRIVIA or (
            last_action == SteerAction.HOLD_SCOPE and need in {NeedKind.OTHER, NeedKind.TOPIC}
        ):
            return SteerAction.HOLD_SCOPE
        if need == NeedKind.JOKE:
            return SteerAction.JOKE_BEAT
        return SteerAction.DEFER_LIGHT

    return SteerAction.DEFER_LIGHT


def _facts(
    state: TutorState,
    utterance: str,
    progress: dict[str, object],
    action: SteerAction,
) -> str:
    said = soften_student_text(utterance)[:180]
    bits = [f'they just said: "{said}"' if said else "utterance empty"]
    if state.last_need_kind:
        bits.append(f"previous_need={state.last_need_kind}")
    if state.last_steer_action:
        bits.append(f"previous_action={state.last_steer_action}")
    minutes = progress["minutes"]
    if minutes is None:
        bits.append("session_duration=unknown — do not mention how long they have been studying")
    else:
        bits.append(f"session_so_far≈{int(minutes)} minutes")
    bits.append(f"student_turns={state.student_turns}")
    bits.append(f"phase={state.phase}")
    if action == SteerAction.RESUME_LESSON and state.topic_title:
        bits.append(f"resume_topic={state.topic_title}")
    if progress["mid_task"]:
        bits.append("mid-task")
    if progress["almost_done"]:
        bits.append("lesson-marked-completed")
    if state.last_confusion_focus:
        bits.append(f"earlier-struggle={state.last_confusion_focus[:120]}")
    else:
        bits.append("no earlier-struggle on record — do not invent prior talk")
    return "; ".join(bits)


_ACTION_STRATEGY: dict[SteerAction, str] = {
    SteerAction.GRANT_PAUSE: (
        "Chosen action: GRANT_PAUSE. Priority 1: a real physical or emotional need. "
        "Acknowledge it and let them go. Offer one concrete next step: go take care "
        "of it, take a short while, and message when they are back — you will wait. "
        "Do NOT teach. Do NOT quiz. Do NOT redirect. Do NOT name the topic, slide, "
        "lemma, formula, or next lesson step. Do NOT tell them to go and also keep "
        "studying. One decision only. If they name a break length, acknowledge that "
        "wish and offer a short limit in fresh words — never reuse your last sentence."
    ),
    SteerAction.CONFIRM_PAUSE: (
        "Chosen action: CONFIRM_PAUSE. They are still on the break conversation — "
        "a repeat of the need, or a pushback on length. Do NOT teach. Do NOT quiz. "
        "Do NOT redirect to the lesson. Do NOT name the topic, slide, lemma, or formula. "
        "If they asked for a longer break than you can hold, briefly acknowledge that "
        "counter-offer, then restate a short limit in NEW words. Never repeat the "
        "sentence you used last turn. Then one concrete next step: start when they "
        "are ready, or message when back."
    ),
    SteerAction.FINISH_THEN_PAUSE: (
        "Chosen action: FINISH_THEN_PAUSE. A genuine rest need arrived mid-task. "
        "Acknowledge the need as real, then make finishing this one bit the condition. "
        "You MAY name the current topic once, as the thing being finished. "
        "Do NOT teach the concept. Do NOT quote any formula."
    ),
    SteerAction.DEFER_LIGHT: (
        "Chosen action: DEFER_LIGHT. First light tangent. A brief warm or witty nod "
        "to the specific thing they asked is fine — this is low-stakes, not a need. "
        "Do NOT answer the off-topic ask. Do NOT ask any follow-up about the tangent "
        "(which movie, what game, etc.). Do NOT grant a break. You MAY name the "
        "current topic once. Then immediately re-engage the slide with one hook."
    ),
    SteerAction.HOLD_FIRM: (
        "Chosen action: HOLD_FIRM. They have already been asked whether the topic "
        "is the problem and they are still pushing away. Kindly hold the line. "
        "You MAY name the current topic once. Do NOT answer the question. "
        "Do NOT answer the off-topic ask. "
        "Do NOT teach a full explanation. Do NOT quote formulas. Do NOT mock. "
        "Then one fresh hook back into the slide. No pause this turn."
    ),
    SteerAction.HOLD_SCOPE: (
        "Chosen action: HOLD_SCOPE. They asked something outside this lesson "
        "(politics, sports, trivia, general chat, other subjects). "
        "Do NOT answer the question. Do NOT provide the fact they asked for. "
        "A brief warm nod that you heard the question, then refuse it. "
        "You MAY name the current topic once. Then immediately re-engage the "
        "slide with one hook. Do NOT quote formulas."
    ),
    SteerAction.CHECK_IN: (
        "Chosen action: CHECK_IN. They have deflected more than once in a row. "
        "Ask this diagnose question only once this episode. "
        "Stop mechanical redirecting. Do NOT answer the question. Do NOT answer "
        "the off-topic ask. Do NOT "
        "teach the definition. Do NOT grant a break yet. Name that they have "
        "pulled toward a few different things, then ask whether the current topic "
        "is confusing, boring, or hard to follow right now. Wait for that answer. "
        "The next turn will adapt — an active task if boring, a smaller step if "
        "confusing — based on what they say. Do not invent which of those it is."
    ),
    SteerAction.CONFIRM_DONE: (
        "Chosen action: CONFIRM_DONE. They pushed you away after you already "
        "tried to re-engage. Do not go silent and do not teach. "
        "One short line only: ask whether they want to stop the session now, or "
        "whether the last attempt still did not click. No pushback. Then wait."
    ),
    SteerAction.JOKE_BEAT: (
        "Chosen action: JOKE_BEAT. React to the joke like a friendly teacher. "
        "Do not teach. Do not name the topic or formula."
    ),
    SteerAction.GRANT_LEAVE: (
        "Chosen action: GRANT_LEAVE. They need to go. Let them. "
        "Do not teach. Do not name formulas. Do not guilt them."
    ),
    SteerAction.RESUME_LESSON: (
        "Chosen action: RESUME_LESSON. They are back and have signalled they are "
        "ready. Welcome them briefly. You may name the topic now because you are "
        "resuming. Do not dump the formula or re-teach. Ask if they are ready to continue."
    ),
}


def _deviation_shape_note(action: SteerAction) -> str:
    """The beats a redirect must hit, described rather than quoted.

    A quoted phrase in this prompt gets copied verbatim. Name the beats, leave
    the wording free. A fence-only reply that just tells them to focus is the
    failure mode — the redirect has to pull them back into the slide.
    """
    if action == SteerAction.CHECK_IN:
        return (
            "This reply is a check-in, not a fence. Do not add a lesson hook and "
            "do not offer a break. One question about their state, then wait. "
        )
    if action not in SCOPE_HOLD_ACTIONS:
        return ""
    return (
        "Shape this reply in beats. First, a brief warm nod to the specific thing "
        "they just asked — a touch of wit is fine for movies, games, or trivia, "
        "never for hunger, tiredness, or distress. Second, do not answer the "
        "off-topic ask. Third, immediately re-engage the current slide with one "
        "hook: a small question, a real-world tease, or one concrete next step. "
        "The hook must be about the lesson, never a follow-up about the tangent. "
        "Never end on a fence-only line that only tells them to focus. "
        "Do not offer a break, do not say you will wait, and do not tell them to "
        "come back when they are ready. "
    )


def _firmness_note(action: SteerAction, consecutive: int) -> str:
    """How this redirect should feel relative to the last one.

    Deliberately quote no sample sentences. A quoted phrase gets copied
    verbatim, which is how one stock line took over every turn.
    """
    if action not in SCOPE_HOLD_ACTIONS:
        return ""
    if action == SteerAction.CHECK_IN:
        return (
            "They have already been redirected at least once. Do not repeat that "
            "redirect. Ask about the topic itself. "
        )
    if consecutive <= 0:
        return (
            "This is their first drift — keep it light, warm, and brief. "
            "Respond to the specific thing they just said, in your own words. "
        )
    return (
        "They keep pushing. Stay warm. Do not become rude, sarcastic, or robotic. "
        "Say it differently from your last reply. "
    )


def steering_strategy(
    state: TutorState,
    utterance: str,
    *,
    consecutive: int,
    topic_shift: bool = False,
    now: float | None = None,
) -> tuple[SteerAction, str]:
    action = choose_steer_action(
        state,
        utterance,
        consecutive=consecutive,
        topic_shift=topic_shift,
        now=now,
    )
    progress = _lesson_progress(state, now=now)
    need = classify_need(utterance, topic_shift=topic_shift)
    body = _ACTION_STRATEGY[action]
    shape = _deviation_shape_note(action)
    firmness = _firmness_note(action, consecutive)
    return action, (
        "This turn is a conversational judgment, not a lesson dump. "
        f"Need kind: {need.value}. {body} {shape}{firmness}"
        "Do not answer movie plots, scores, trivia, news, or general chat. "
        "Do not open with a stock empathy preface — start from the thing they said. "
        "Your own previous reply is in the conversation above: do not reuse its "
        "wording, its opening, or its shape, and never fall back on a fixed template. "
        "Vary how you say this every turn. Repeating the same redirect pattern is "
        "a failure. "
        "Speak to the specific thing they just asked for, not to off-topic requests "
        "in general — a reply that would fit any interruption is the wrong reply. "
        "Do not invent duration, feelings, or earlier talk. "
        "Teenage Class 10 tone: conversational, not childish, usually no emoji. "
        "One or two spoken sentences. "
        f"Facts you may use: {_facts(state, utterance, progress, action)}."
    )


def resume_strategy(state: TutorState) -> str:
    progress = _lesson_progress(state)
    topic = state.topic_title or "where we stopped"
    return (
        f"{_ACTION_STRATEGY[SteerAction.RESUME_LESSON]} "
        f"You may mention {topic} only as the resume point. "
        "Do not invent how long they were gone. "
        f"Facts you may use: {_facts(state, "I'm back", progress, SteerAction.RESUME_LESSON)}."
    )


def steer_note(action: SteerAction) -> str:
    return f"{STEER_NOTE_PREFIX}{action.value}"
