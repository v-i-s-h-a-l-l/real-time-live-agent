"""Smart study breaks — structured pause, not an LLM-owned timer.

The student can ask for a 1–5 minute rest. Intent is parsed here (no extra
LLM call). The application owns start/end timestamps and fires BREAK_END
once. Tutoring state (lesson, question, conversation, page context) is
never modified.

Limitation: break state lives on the in-memory voice session. A page
refresh or new WebSocket connection starts IDLE — there is no database
persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger

from tutor.intent import is_hostile_to_tutor

MAX_BREAK_MINUTES: int = 5
SUPPORTED_BREAK_MINUTES: tuple[int, ...] = (1, 2, 3, 4, 5)
MAX_BREAK_SECONDS: int = MAX_BREAK_MINUTES * 60
MS_PER_SECOND: int = 1000
# Non-duration replies while asking "how long?" before we drop the state.
MAX_NEGOTIATION_MISSES: int = 2

# Spoken number words we accept for 1–5 and for rejecting longer asks.
_NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "forty-five": 45,
    "fortyfive": 45,
    "sixty": 60,
}

_MINUTE_HYPHEN: dict[int, str] = {
    1: "one-minute",
    2: "two-minute",
    3: "three-minute",
    4: "four-minute",
    5: "five-minute",
}

_MINUTE_SPOKEN: dict[int, str] = {
    1: "one minute",
    2: "two minutes",
    3: "three minutes",
    4: "four minutes",
    5: "five minutes",
}


class BreakPhase(str, Enum):
    IDLE = "idle"
    REQUESTING_DURATION = "requesting_duration"
    OFFERING_MAX = "offering_max"
    ACTIVE = "active"


class BreakKind(str, Enum):
    NONE = "none"
    REQUEST_NO_DURATION = "request_no_duration"
    REQUEST_VALID = "request_valid"
    REQUEST_INVALID = "request_invalid"
    DURATION_ONLY = "duration_only"
    ACCEPT_OFFER = "accept_offer"
    DECLINE_OFFER = "decline_offer"
    RESUME = "resume"
    EXTEND = "extend"
    ALREADY_ACTIVE = "already_active"
    DURING_CHAT = "during_chat"


@dataclass(frozen=True)
class ParsedDuration:
    """A duration the student mentioned, before 1–5 validation."""

    minutes: int | None
    seconds: int | None
    invalid_reason: str | None = None

    @property
    def is_supported(self) -> bool:
        return (
            self.invalid_reason is None
            and self.seconds is None
            and self.minutes in SUPPORTED_BREAK_MINUTES
        )


@dataclass
class BreakState:
    phase: BreakPhase = BreakPhase.IDLE
    duration_minutes: int | None = None
    started_at: float | None = None  # unix seconds
    ends_at: float | None = None  # unix seconds
    during_break_replied: bool = False
    negotiation_misses: int = 0

    @property
    def active(self) -> bool:
        return self.phase == BreakPhase.ACTIVE

    def remaining_seconds(self, now: float) -> float:
        if self.ends_at is None:
            return 0.0
        return max(0.0, self.ends_at - now)

    def snapshot(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "durationMinutes": self.duration_minutes,
            "startedAt": _to_millis(self.started_at),
            "endsAt": _to_millis(self.ends_at),
            "phase": self.phase.value,
        }


@dataclass(frozen=True)
class BreakUtterance:
    kind: BreakKind
    minutes: int | None = None
    parsed: ParsedDuration | None = None


@dataclass(frozen=True)
class BreakTurnResult:
    """What the processor should do for this student turn (or timer fire)."""

    swallow: bool
    spoken: str
    event: dict[str, Any]
    drop_last_user: bool = False
    schedule: bool = False
    cancel_timer: bool = False


# ── Wire event types (mirrored in tutor-frontend protocol.ts) ────────────────

EVENT_BREAK_STARTED = "break_started"
EVENT_BREAK_ENDED = "break_ended"
EVENT_BREAK_CANCELLED = "break_cancelled"
EVENT_BREAK_REQUESTING = "break_requesting"
EVENT_BREAK_MESSAGE = "break_message"

BREAK_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_BREAK_STARTED,
        EVENT_BREAK_ENDED,
        EVENT_BREAK_CANCELLED,
        EVENT_BREAK_REQUESTING,
        EVENT_BREAK_MESSAGE,
    }
)


# ── NLU ──────────────────────────────────────────────────────────────────────

# "break it down" is a teaching ask, not a study break.
_NOT_STUDY_BREAK = re.compile(
    r"\bbreak(?:\s+it)?\s+down\b|\bbreakthrough\b|\bbreak\s+the\b",
    re.I,
)

_BREAK_WORD = re.compile(r"\b(break|rest)\b", re.I)

_REQUEST_CUE = re.compile(
    r"\b("
    r"i\s+(?:want|need|could\s+use)|"
    r"can\s+i\s+(?:have|take|get|rest|break)|"
    r"could\s+i\s+(?:have|take|rest|break)|"
    r"give\s+me|"
    r"let'?s\s+(?:take|have)|"
    r"allow\s+me|"
    r"i\s+want\s+to\s+rest"
    r")\b",
    re.I,
)

# Bare "break"/"rest" is not a request. "why are you asking about a break"
# must not start or continue duration negotiation.
_EXPLICIT_BREAK_ASK = re.compile(
    r"("
    r"\b(?:take|need|want|having|have|had)\s+(?:a\s+)?(?:quick\s+)?(?:break|rest)\b|"
    r"\b(?:break|rest)\s+please\b|"
    r"\btime\s+for\s+(?:a\s+)?(?:break|rest)\b|"
    r"\b(?:break|rest)\s+time\b"
    r")",
    re.I,
)

# Math confirmation / working must never look like a study-break ask.
_MATH_TALK = re.compile(
    r"("
    r"\bam\s+i\s+right\b|"
    r"\bis\s+(?:that|this|it)\s+(?:right|correct)\b|"
    r"\bequals?\b|"
    r"\bplus\b|"
    r"\bminus\b|"
    r"\btimes\b|"
    r"\bdivided\s+by\b|"
    r"\bremainder\b|"
    r"\bquotient\b|"
    r"\bdivisor\b"
    r")",
    re.I,
)

# Pushback, decline, or "why are you talking about a break" while negotiating.
_NEGOTIATION_ESCAPE = re.compile(
    r"("
    r"\bi\s+don'?t\s+want\s+(?:a\s+|to\s+)?(?:break|rest)\b|"
    r"\bdon'?t\s+(?:want|need|give\s+me)\s+(?:a\s+|to\s+)?(?:break|rest)\b|"
    r"\bno\s+(?:break|rest)\b|"
    r"\bnot\s+(?:asking\s+for\s+|wanting\s+)?(?:a\s+)?(?:break|rest)\b|"
    r"\bwhy\s+(?:are\s+you|would\s+you|do\s+you)\b.{0,80}\b(?:break|rest)\b|"
    r"\b(?:break|rest)\b.{0,80}\bwhy\s+(?:are\s+you|would\s+you|do\s+you)\b|"
    r"\bwhy\s+(?:ask|asking|give|giving)\b.{0,80}\b(?:break|rest)\b|"
    r"\bstop\s+(?:asking|giving|talking)\b.{0,80}\b(?:break|rest)\b|"
    r"\bdesperately\b.{0,40}\b(?:break|rest)\b|"
    r"\b(?:break|rest)\b.{0,40}\bdesperately\b|"
    r"\bwhat\s+the\s+(?:fuck|hell)\b"
    r")",
    re.I,
)

_RESUME = re.compile(
    r"("
    r"\bi(?:'?m|\s+am)\s+back\b|"
    r"\bi(?:'?m|\s+am)\s+ready\b|"
    r"\bi\s+changed\s+my\s+mind\b|"
    r"\bi\s+want\s+to\s+continue\b|"
    r"\bwant\s+to\s+continue\s+with\s+(?:the\s+)?(?:maths?|math|lesson)\b|"
    r"\blet'?s\s+(?:continue|go\s+back|get\s+back|resume)\b|"
    r"\bend\s+(?:the\s+)?break\b|"
    r"\bi\s+don'?t\s+need\s+(?:the\s+)?break\b|"
    r"\bready\s+to\s+(?:continue|go\s+back|resume)\b|"
    r"\bcontinue\s+(?:with\s+)?(?:the\s+)?(?:lesson|class|maths?|math)\b"
    r")",
    re.I,
)

_EXTEND_CUE = re.compile(
    r"\b(another|extend|more\s+time|add)\b",
    re.I,
)

_YES = re.compile(
    r"^\s*(yes|yeah|yep|sure|ok(?:ay)?|please|five(?:\s+minutes?)?)\s*[.!?]?\s*$",
    re.I,
)

_NO = re.compile(
    r"^\s*(no|nope|nah|not\s+now|never\s+mind|cancel)\s*[.!?]?\s*$",
    re.I,
)

_HALF_HOUR = re.compile(
    r"\b(half\s+an\s+hour|an\s+hour|\d+\s+hours?)\b",
    re.I,
)

_DURATION = re.compile(
    r"\b(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|fifteen|twenty|thirty|forty|forty-?five|sixty)\s*-?\s*"
    r"(?P<unit>minutes?|mins?|seconds?|secs?)\b",
    re.I,
)

_BARE_NUMBER = re.compile(
    r"^\s*(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[.!?]?\s*$",
    re.I,
)

# Phone-step-away idioms that CallMute already owns. Do not steal them
# as study-break starts unless the student also said "break"/"rest".
_MUTE_IDIOM = re.compile(
    r"("
    r"\bgive\s+me\s+a\s+(sec|second|moment|minute)\b|"
    r"\bone\s+(sec|second|moment|min|minute)\b|"
    r"\bjust\s+a\s+(sec|second|moment|min)\b|"
    r"\ba\s+minute\b"
    r")",
    re.I,
)


def _to_millis(epoch_seconds: float | None) -> int | None:
    if epoch_seconds is None:
        return None
    return int(epoch_seconds * MS_PER_SECOND)


def _parse_number_token(token: str) -> int | None:
    token = token.strip().lower().replace(" ", "")
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token.replace("-", ""))


def parse_duration(text: str) -> ParsedDuration | None:
    """Extract a duration mention, or None if the utterance has none."""
    raw = text or ""
    if _HALF_HOUR.search(raw):
        return ParsedDuration(minutes=30, seconds=None, invalid_reason="too_long")

    match = _DURATION.search(raw)
    if not match:
        return None

    amount = _parse_number_token(match.group("num"))
    if amount is None:
        return None
    unit = match.group("unit").lower()
    if unit.startswith("sec"):
        return ParsedDuration(minutes=None, seconds=amount, invalid_reason="seconds")
    if amount in SUPPORTED_BREAK_MINUTES:
        return ParsedDuration(minutes=amount, seconds=None)
    return ParsedDuration(minutes=amount, seconds=None, invalid_reason="too_long")


def parse_bare_duration(text: str) -> ParsedDuration | None:
    """'Two minutes' already handled; this is a lone 'two' / '2'."""
    match = _BARE_NUMBER.match(text or "")
    if not match:
        return None
    amount = _parse_number_token(match.group("num"))
    if amount is None:
        return None
    if amount in SUPPORTED_BREAK_MINUTES:
        return ParsedDuration(minutes=amount, seconds=None)
    return ParsedDuration(minutes=amount, seconds=None, invalid_reason="too_long")


def _has_break_word(text: str) -> bool:
    if _NOT_STUDY_BREAK.search(text):
        return False
    return bool(_BREAK_WORD.search(text))


def _is_explicit_break_request(text: str, *, has_break: bool, request_cue: bool) -> bool:
    """True only when the student is actually asking to pause studying."""
    if not has_break:
        return False
    if _NEGOTIATION_ESCAPE.search(text) or is_hostile_to_tutor(text):
        return False
    return request_cue or bool(_EXPLICIT_BREAK_ASK.search(text))


def classify_utterance(text: str, phase: BreakPhase) -> BreakUtterance:
    """Map a finalized student utterance onto a break action.

    Duration-only answers ("two minutes") are ignored unless we already
    asked how long. Idle "one minute" stays with CallMute.
    """
    utterance = (text or "").strip()
    if not utterance:
        return BreakUtterance(BreakKind.NONE)

    duration = parse_duration(utterance)
    has_break = _has_break_word(utterance)
    request_cue = bool(_REQUEST_CUE.search(utterance))
    explicit_request = _is_explicit_break_request(
        utterance, has_break=has_break, request_cue=request_cue
    )
    math_talk = bool(_MATH_TALK.search(utterance))
    escape = bool(_NEGOTIATION_ESCAPE.search(utterance) or is_hostile_to_tutor(utterance))

    if phase == BreakPhase.ACTIVE:
        if _EXTEND_CUE.search(utterance) and duration is not None:
            return BreakUtterance(
                BreakKind.EXTEND,
                minutes=duration.minutes if duration.is_supported else None,
                parsed=duration,
            )
        if _RESUME.search(utterance):
            return BreakUtterance(BreakKind.RESUME)
        if is_hostile_to_tutor(utterance) or (
            _NEGOTIATION_ESCAPE.search(utterance) and has_break
        ):
            return BreakUtterance(BreakKind.RESUME)
        if has_break or request_cue or duration is not None:
            return BreakUtterance(
                BreakKind.ALREADY_ACTIVE,
                minutes=duration.minutes if duration and duration.is_supported else None,
                parsed=duration,
            )
        return BreakUtterance(BreakKind.DURING_CHAT)

    if phase in (BreakPhase.REQUESTING_DURATION, BreakPhase.OFFERING_MAX):
        if escape or (math_talk and not explicit_request):
            return BreakUtterance(BreakKind.NONE)
        if _RESUME.search(utterance):
            return BreakUtterance(BreakKind.DECLINE_OFFER)
        if phase == BreakPhase.OFFERING_MAX and _YES.match(utterance):
            return BreakUtterance(BreakKind.ACCEPT_OFFER, minutes=MAX_BREAK_MINUTES)
        if _NO.match(utterance):
            return BreakUtterance(BreakKind.DECLINE_OFFER)

        answer = duration or parse_bare_duration(utterance)
        if answer is not None:
            if answer.is_supported:
                return BreakUtterance(
                    BreakKind.DURATION_ONLY, minutes=answer.minutes, parsed=answer
                )
            return BreakUtterance(BreakKind.REQUEST_INVALID, parsed=answer)

        if explicit_request:
            return BreakUtterance(BreakKind.REQUEST_NO_DURATION)

        # Mentioning "break" again is not a duration. Let the LLM hear it.
        return BreakUtterance(BreakKind.NONE)

    # Idle.
    if escape or (math_talk and not explicit_request):
        return BreakUtterance(BreakKind.NONE)

    if _RESUME.search(utterance) and not has_break:
        return BreakUtterance(BreakKind.NONE)

    if explicit_request:
        if duration is None:
            return BreakUtterance(BreakKind.REQUEST_NO_DURATION)
        if duration.is_supported:
            return BreakUtterance(
                BreakKind.REQUEST_VALID, minutes=duration.minutes, parsed=duration
            )
        return BreakUtterance(BreakKind.REQUEST_INVALID, parsed=duration)

    # "I need two minutes" / "Can I have 3 minutes?" without the word break.
    if request_cue and duration is not None:
        if _MUTE_IDIOM.search(utterance):
            return BreakUtterance(BreakKind.NONE)
        if duration.is_supported:
            return BreakUtterance(
                BreakKind.REQUEST_VALID, minutes=duration.minutes, parsed=duration
            )
        return BreakUtterance(BreakKind.REQUEST_INVALID, parsed=duration)

    return BreakUtterance(BreakKind.NONE)


def should_skip_call_mute(text: str, phase: BreakPhase) -> bool:
    """True when CallMute must not steal this utterance from the break flow."""
    kind = classify_utterance(text, phase).kind
    return kind != BreakKind.NONE


# ── Spoken copy ──────────────────────────────────────────────────────────────

def minute_hyphen(minutes: int) -> str:
    return _MINUTE_HYPHEN.get(minutes, f"{minutes}-minute")


def spoken_ask_duration() -> str:
    return (
        f"Sure. How long would you like? You can take up to "
        f"{_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}."
    )


def spoken_invalid_duration() -> str:
    return (
        f"I can give you a break of up to {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}. "
        f"Would you like {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}?"
    )


def spoken_invalid_long() -> str:
    return (
        f"I can give you up to {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]} here. "
        f"Would you like {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}?"
    )


def spoken_invalid_seconds() -> str:
    return (
        f"I can give you a break of one to {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}. "
        "How long would you like?"
    )


def spoken_break_started(minutes: int) -> str:
    return (
        f"Sure, take a {minute_hyphen(minutes)} break. "
        "I'll let you know when it's over."
    )


def spoken_break_ended(minutes: int) -> str:
    return (
        f"Hey, your {minute_hyphen(minutes)} break is over. "
        "Ready to get back to the lesson?"
    )


def spoken_cancelled() -> str:
    return "Welcome back. Let's continue."


def spoken_declined() -> str:
    return "Okay, let's keep going."


def spoken_still_on_break() -> str:
    return "You're still on your break. I'll be ready when your break is over."


def format_remaining_spoken(seconds: float) -> str:
    if seconds >= 90:
        minutes = max(1, round(seconds / 60))
        if minutes == 1:
            return "about one minute"
        if minutes in _MINUTE_SPOKEN:
            return f"about {_MINUTE_SPOKEN[minutes]}"
        return f"about {minutes} minutes"
    if seconds >= 45:
        return "about a minute"
    if seconds >= 15:
        return f"about {int(seconds)} seconds"
    return "less than half a minute"


def spoken_already_active(remaining_seconds: float, *, offer_extend: bool) -> str:
    left = format_remaining_spoken(remaining_seconds)
    line = f"You're already on a break. Your current break has {left} left."
    if offer_extend:
        line += (
            f" You can extend it, up to a total of "
            f"{_MINUTE_SPOKEN[MAX_BREAK_MINUTES]}."
        )
    return line


def spoken_extended(minutes: int) -> str:
    return (
        f"Okay, I'll give you until a {minute_hyphen(minutes)} total. "
        "I'll let you know when it's over."
    )


def spoken_cannot_extend() -> str:
    return (
        f"I can only give you {_MINUTE_SPOKEN[MAX_BREAK_MINUTES]} in total. "
        "I'll let you know when this break is over."
    )


def _invalid_spoken(parsed: ParsedDuration | None) -> str:
    if parsed is not None and parsed.invalid_reason == "seconds":
        return spoken_invalid_seconds()
    if parsed is not None and parsed.minutes is not None and parsed.minutes >= 30:
        return spoken_invalid_long()
    return spoken_invalid_duration()


def _event(
    event_type: str,
    *,
    spoken: str,
    duration_minutes: int | None = None,
    started_at: float | None = None,
    ends_at: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": event_type, "spoken": spoken}
    if duration_minutes is not None:
        payload["durationMinutes"] = duration_minutes
    started_ms = _to_millis(started_at)
    ends_ms = _to_millis(ends_at)
    if started_ms is not None:
        payload["startedAt"] = started_ms
    if ends_ms is not None:
        payload["endsAt"] = ends_ms
    return payload


# ── State machine ────────────────────────────────────────────────────────────

class BreakStore:
    """Per-session break state. The processor schedules the timer around this."""

    def __init__(self) -> None:
        self.state = BreakState()
        self.generation: int = 0
        self._last_spoken: str = ""

    def should_skip_mute(self, text: str) -> bool:
        return should_skip_call_mute(text, self.state.phase)

    def remaining_seconds(self, now: float) -> float:
        return self.state.remaining_seconds(now)

    def apply(self, utterance: str, now: float) -> BreakTurnResult | None:
        text = (utterance or "").strip()
        if not text:
            return None
        classified = classify_utterance(text, self.state.phase)
        negotiating = self.state.phase in (
            BreakPhase.REQUESTING_DURATION,
            BreakPhase.OFFERING_MAX,
        )
        if classified.kind == BreakKind.NONE:
            if negotiating:
                logger.warning(
                    "[BreakStore] unmatched reply while negotiating duration; "
                    "clearing state so the LLM can handle the current message"
                )
                self.state = BreakState()
            return None

        if (
            negotiating
            and classified.kind == BreakKind.REQUEST_NO_DURATION
        ):
            self.state.negotiation_misses += 1
            logger.warning(
                "[BreakStore] ignoring repeat duration-ask while already negotiating"
            )
            if self.state.negotiation_misses >= MAX_NEGOTIATION_MISSES:
                self.state = BreakState()
            return None

        handler = {
            BreakKind.REQUEST_NO_DURATION: self._ask_duration,
            BreakKind.REQUEST_VALID: self._start_from_request,
            BreakKind.REQUEST_INVALID: self._offer_max,
            BreakKind.DURATION_ONLY: self._start_from_duration,
            BreakKind.ACCEPT_OFFER: self._accept_max,
            BreakKind.DECLINE_OFFER: self._decline,
            BreakKind.RESUME: self._cancel,
            BreakKind.EXTEND: self._extend,
            BreakKind.ALREADY_ACTIVE: self._already_active,
            BreakKind.DURING_CHAT: self._during_chat,
        }[classified.kind]
        result = handler(classified, now)
        if result is not None and result.spoken:
            if (
                result.spoken == self._last_spoken
                and classified.kind == BreakKind.REQUEST_NO_DURATION
            ):
                logger.error(
                    "[BreakStore] blocked identical duration-ask reply; passing through to LLM"
                )
                if self.state.phase in (
                    BreakPhase.REQUESTING_DURATION,
                    BreakPhase.OFFERING_MAX,
                ):
                    self.state = BreakState()
                return None
            self._last_spoken = result.spoken
        return result

    def expire(self, now: float, generation: int) -> BreakTurnResult | None:
        """Fire BREAK_END once. Stale generations are ignored."""
        del now  # end time is already stored; `now` kept for the timer contract
        if generation != self.generation:
            return None
        if self.state.phase != BreakPhase.ACTIVE:
            return None
        minutes = self.state.duration_minutes or 1
        spoken = spoken_break_ended(minutes)
        event = _event(
            EVENT_BREAK_ENDED,
            spoken=spoken,
            duration_minutes=minutes,
            started_at=self.state.started_at,
            ends_at=self.state.ends_at,
        )
        self.generation += 1
        self.state = BreakState()
        return BreakTurnResult(swallow=True, spoken=spoken, event=event)

    def reset(self) -> None:
        """Drop in-memory break state (disconnect / new connection)."""
        self.generation += 1
        self.state = BreakState()
        self._last_spoken = ""

    def clear_negotiation(self) -> None:
        """Drop duration-ask state without touching an active timed break."""
        if self.state.phase in (
            BreakPhase.REQUESTING_DURATION,
            BreakPhase.OFFERING_MAX,
        ):
            self.state = BreakState()
        self._last_spoken = ""

    def _ask_duration(self, _classified: BreakUtterance, _now: float) -> BreakTurnResult:
        self.state = BreakState(phase=BreakPhase.REQUESTING_DURATION)
        spoken = spoken_ask_duration()
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(EVENT_BREAK_REQUESTING, spoken=spoken),
            cancel_timer=True,
        )

    def _start_from_request(self, classified: BreakUtterance, now: float) -> BreakTurnResult:
        return self._start(classified.minutes or 1, now)

    def _start_from_duration(self, classified: BreakUtterance, now: float) -> BreakTurnResult:
        return self._start(classified.minutes or 1, now)

    def _accept_max(self, _classified: BreakUtterance, now: float) -> BreakTurnResult:
        return self._start(MAX_BREAK_MINUTES, now)

    def _offer_max(self, classified: BreakUtterance, _now: float) -> BreakTurnResult:
        self.state = BreakState(phase=BreakPhase.OFFERING_MAX)
        spoken = _invalid_spoken(classified.parsed)
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(EVENT_BREAK_REQUESTING, spoken=spoken),
            cancel_timer=True,
        )

    def _decline(self, _classified: BreakUtterance, _now: float) -> BreakTurnResult:
        was_active = self.state.phase == BreakPhase.ACTIVE
        self.generation += 1
        self.state = BreakState()
        spoken = spoken_cancelled() if was_active else spoken_declined()
        event_type = EVENT_BREAK_CANCELLED if was_active else EVENT_BREAK_MESSAGE
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(event_type, spoken=spoken),
            cancel_timer=True,
        )

    def _cancel(self, _classified: BreakUtterance, _now: float) -> BreakTurnResult:
        minutes = self.state.duration_minutes
        self.generation += 1
        self.state = BreakState()
        spoken = spoken_cancelled()
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(
                EVENT_BREAK_CANCELLED,
                spoken=spoken,
                duration_minutes=minutes,
            ),
            cancel_timer=True,
        )

    def _already_active(self, classified: BreakUtterance, now: float) -> BreakTurnResult:
        remaining = self.state.remaining_seconds(now)
        offer = classified.kind == BreakKind.ALREADY_ACTIVE
        spoken = spoken_already_active(remaining, offer_extend=offer)
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(EVENT_BREAK_MESSAGE, spoken=spoken),
            drop_last_user=True,
        )

    def _extend(self, classified: BreakUtterance, now: float) -> BreakTurnResult:
        if self.state.started_at is None or self.state.ends_at is None:
            return self._already_active(classified, now)

        max_end = self.state.started_at + MAX_BREAK_SECONDS
        if self.state.ends_at >= max_end - 0.5:
            spoken = spoken_cannot_extend()
            return BreakTurnResult(
                swallow=True,
                spoken=spoken,
                event=_event(EVENT_BREAK_MESSAGE, spoken=spoken),
                drop_last_user=True,
            )

        extra = classified.minutes
        if extra is None or not classified.parsed or not classified.parsed.is_supported:
            spoken = spoken_already_active(
                self.state.remaining_seconds(now), offer_extend=True
            )
            return BreakTurnResult(
                swallow=True,
                spoken=spoken,
                event=_event(EVENT_BREAK_MESSAGE, spoken=spoken),
                drop_last_user=True,
            )

        requested_end = now + extra * 60
        new_end = min(max_end, max(self.state.ends_at, requested_end))
        self.state.ends_at = new_end
        total = max(1, round((new_end - self.state.started_at) / 60))
        total = min(total, MAX_BREAK_MINUTES)
        self.state.duration_minutes = total
        self.generation += 1
        spoken = spoken_extended(total)
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(
                EVENT_BREAK_STARTED,
                spoken=spoken,
                duration_minutes=total,
                started_at=self.state.started_at,
                ends_at=self.state.ends_at,
            ),
            drop_last_user=True,
            schedule=True,
            cancel_timer=True,
        )

    def _during_chat(self, _classified: BreakUtterance, _now: float) -> BreakTurnResult:
        if self.state.during_break_replied:
            return BreakTurnResult(
                swallow=True,
                spoken="",
                event={},
                drop_last_user=True,
            )
        self.state.during_break_replied = True
        spoken = spoken_still_on_break()
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(EVENT_BREAK_MESSAGE, spoken=spoken),
            drop_last_user=True,
        )

    def _start(self, minutes: int, now: float) -> BreakTurnResult:
        minutes = int(minutes)
        if minutes not in SUPPORTED_BREAK_MINUTES:
            return self._offer_max(
                BreakUtterance(
                    BreakKind.REQUEST_INVALID,
                    parsed=ParsedDuration(minutes=minutes, seconds=None, invalid_reason="too_long"),
                ),
                now,
            )
        self.generation += 1
        ends_at = now + minutes * 60
        self.state = BreakState(
            phase=BreakPhase.ACTIVE,
            duration_minutes=minutes,
            started_at=now,
            ends_at=ends_at,
            during_break_replied=False,
        )
        spoken = spoken_break_started(minutes)
        return BreakTurnResult(
            swallow=True,
            spoken=spoken,
            event=_event(
                EVENT_BREAK_STARTED,
                spoken=spoken,
                duration_minutes=minutes,
                started_at=now,
                ends_at=ends_at,
            ),
            schedule=True,
            cancel_timer=True,
        )
