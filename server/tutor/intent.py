"""Deterministic student-intent heuristics — no extra LLM call."""

from __future__ import annotations

import re

from tutor.types import StudentIntent

_CONFUSION = re.compile(
    r"("
    r"\bi\s+(?:still\s+)?don'?t understand\b|"
    r"\bdont understand\b|"
    r"\bdon'?t get it\b|"
    r"\bstill don'?t get\b|"
    r"\bconfused\b|"
    r"\bi'?m lost\b|"
    r"\bnot getting\b|"
    r"\bdoesn'?t make sense\b|"
    r"\bsamajh nahi\b|"
    r"समझ नहीं|"
    r"புரியல|"
    r"\bpuriyala\b"
    r")",
    re.I,
)

_HINT = re.compile(
    r"\b("
    r"hint|clue|help me (a bit|out)|give me a hint|another hint|next hint|"
    r"thoda hint|इशारा"
    r")\b",
    re.I,
)

_ANSWER_REQUEST = re.compile(
    r"\b("
    r"just (give|tell) (me )?the answer|tell me the answer|what(?:'s| is) the answer|"
    r"give me the (final )?answer|solve it for me|don'?t make me guess|"
    r"seedha answer|सीधा जवाब"
    r")\b",
    re.I,
)

_WHY_HOW = re.compile(
    r"^\s*(why|how|how come|what if|when do we|where (?:is|does|do) this)\b|"
    r"\b(why (?:do|did|are|is|we)|how (?:do|does|did|can|to)|kyun|क्यों|ஏன்|எப்படி)\b",
    re.I,
)

_REPEAT = re.compile(
    r"\b("
    r"repeat|say (that|it) again|explain (that|it) again|"
    r"explain (that|it) differently|one more time|"
    r"can you (?:repeat|rephrase)|फिर से|மறுபடி"
    r")\b",
    re.I,
)

_PRACTICE = re.compile(
    r"\b("
    r"another (question|problem|example)|give me (a |another )?(question|problem)|"
    r"practice|try one|next question|"
    r"solve (this|it|the (question|problem|equation))|help me solve|walk me through"
    r")\b",
    re.I,
)

_RELATED = re.compile(
    r"\b("
    r"real life|used in|application|where (?:do|is) (?:this|it) used|"
    r"why (?:is this|do we) (?:important|needed)|exam|board|marks|"
    r"who invented|who discovered|history of|named after"
    r")\b",
    re.I,
)

_UNRELATED = re.compile(
    r"\b("
    r"cricket|football|soccer|tennis|badminton|hockey|ipl|"
    r"dhoni|kohli|sachin|messi|ronaldo|"
    r"bollywood|hollywood|movie|film|netflix|song|celebrity|"
    r"politics|election|prime minister|president|"
    r"news|shopping|amazon|weather|forecast|"
    r"joke|instagram|tiktok|youtube(?: channel)?|"
    r"bitcoin|stock market|match score|"
    r"capital of|who won"
    r")\b",
    re.I,
)

_MATH_KEEP = re.compile(
    r"\b("
    r"maths?|algebra|geometry|polynomial|quadratic|zero|zeros|coefficient|"
    r"equation|formula|root|discriminant|lemma|theorem|integer|prime|"
    r"fraction|triangle|circle|probability|number|variable|example|"
    r"hint|exercise|lesson|chapter|this|that|it|concept"
    r")\b",
    re.I,
)

_TELL_ABOUT = re.compile(
    r"\b(?:tell me about|talk(?: to me)? about|talk(?:\s+\w+){0,3}\s+about)\s+(.+)",
    re.I,
)

_SUCCESS = re.compile(
    r"("
    r"\b(oh+|aha+|aah+)\b.*\b(get it|got it|i see|makes sense)\b|"
    r"\bi (?:finally )?(?:get|got) it\b|"
    r"\bi got the answer\b|"
    r"\bthat makes sense now\b|"
    r"\bi understand now\b|"
    r"^\s*(got it|i see|makes sense)\s*[.!?]?\s*$"
    r")",
    re.I,
)

_HESITATION = re.compile(
    r"("
    r"^\s*(hmm+|hmmm+|uh+|um+|erm+)\s*[.…]*\s*$|"
    r"^\s*(wait|hold on|hang on)\s*[.…!?]*\s*$|"
    r"^\s*(yeah|yes|ok(?:ay)?),?\s*but\s*[.…]*\s*$|"
    r"^\s*(so if|wait,? actually|i think|maybe it'?s|because)\s*[.…]*\s*$"
    r")",
    re.I,
)

_DEPTH_MORE = re.compile(
    r"\b("
    r"explain more|go deeper|more detail|tell me more|say more|"
    r"can you go further|a bit more"
    r")\b",
    re.I,
)

_DEPTH_SHORT = re.compile(
    r"\b("
    r"keep it short|be brief|shorter|too long|"
    r"i already know(?: this)?|i know this already"
    r")\b",
    re.I,
)

_DEPTH_SIMPLER = re.compile(
    r"\b("
    r"simpler example|simpler|too complicated|"
    r"explain like i'?m a beginner|like i'?m (?:a )?beginner|"
    r"eli5|in simple (?:words|terms)"
    r")\b",
    re.I,
)

# Bored / frustrated / done with this step — not a wrong answer, not off-topic.
_DISENGAGEMENT = re.compile(
    r"("
    r"\b(bor(?:ed|ing)|tedious|annoying|frustrating|frustrated)\b|"
    r"\bi(?:'?m| am) (?:so )?(?:bored|tired of this)\b|"
    r"\bthis (?:problem |question |step )?(?:is )?(?:so |very |too )?"
    r"(?:boring|tedious|annoying|frustrating|dull)\b|"
    r"\b(?:don'?t|do not) (?:want|wanna) to (?:do|continue|keep doing) (?:this|it)\b|"
    r"\b(?:not interested|i hate this|tired of this|had enough)\b|"
    r"\b(?:let'?s skip|skip (?:this|it)|move on)\b|"
    r"बोर|ऊब|मन नहीं लग|"
    r"சலிப்பு"
    r")",
    re.I,
)

_MOVE_ON = re.compile(
    r"("
    r"\b(?:skip (?:this|it)|let'?s skip|move on|enough (?:of this|for now))\b|"
    r"\b(?:don'?t|do not) (?:want|wanna) to (?:do|continue|keep doing) (?:this|it)\b"
    r")",
    re.I,
)

_ACK = re.compile(
    r"^\s*(ok(ay)?|yeah|yes|yep|right|exactly|thanks|thank you|"
    r"cool|alright|theek|ठीक|சரி|ஆமா)\s*[.!?]?\s*$",
    re.I,
)

_GREETING = re.compile(
    r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|namaste|vanakkam)\b",
    re.I,
)

_EXPLAIN = re.compile(
    r"\b("
    r"explain|what (?:is|does|are)|tell me about|help me understand|"
    r"walk me through|break(?: it)? down"
    r")\b",
    re.I,
)

_DISAGREE = re.compile(
    r"\b("
    r"that'?s wrong|are you sure|i think it'?s|no,? (?:it'?s|that)|but isn'?t|"
    r"i got a different answer|i think that'?s wrong"
    r")\b",
    re.I,
)

#: "I think it's 2 and 3" is an attempt, not a challenge — but only with a value in it.
_WEAK_DISAGREE = re.compile(r"^\s*i think it'?s\b", re.I)
_ANSWER_VALUE = re.compile(r"(?:^|[\s=(])-?\d+(?:\.\d+)?", re.I)

_STUDENT_ANSWER = re.compile(
    r"("
    r"^\s*(?:is (?:it|the answer)|i (?:got|think)|answer (?:is|=)|x\s*=|roots? (?:are|=))"
    r"|^\s*-?\d+(?:\.\d+)?(?:\s*(?:and|,|or|/|&)\s*-?\d+(?:\.\d+)?)?\s*[.!?]?\s*$"
    r"|^\s*[a-dA-D]\s*[.!?]?\s*$"
    r")",
    re.I,
)

_HELP = re.compile(
    r"\b("
    r"how can you help|what can you (?:do|help)|what do you do|"
    r"how do you help|what are you (?:for|here for)"
    r")\b",
    re.I,
)

_TOPIC_CHANGE = re.compile(
    r"\b("
    r"different topic|another chapter|skip (?:this|to)|let'?s (?:do|move to)|"
    r"change (?:the )?topic|next chapter"
    r")\b",
    re.I,
)

_NAMED_CONCEPT = re.compile(
    r"\b("
    r"quadratic|discriminant|lemma|theorem|formula|algorithm|identity|"
    r"polynomial|remainder|divisor|coefficient|hypotenuse|pythagoras|"
    r"euclid|euclidean|rational|irrational|integer|prime"
    r")\b",
    re.I,
)

_SIMPLE_WHAT = re.compile(r"^\s*(what(?:'s| is)|which is)\b", re.I)

_INTERRUPT_STYLE = re.compile(r"^\s*(wait|hold on|hang on|no wait)\b", re.I)


def detect_intent(utterance: str, *, phase: str = "learning") -> StudentIntent:
    text = (utterance or "").strip()
    if not text:
        return StudentIntent.UNKNOWN

    if _GREETING.search(text) and len(text) < 40:
        return StudentIntent.GREETING
    if _HELP.search(text):
        return StudentIntent.EXPLANATION
    if _SUCCESS.search(text):
        return StudentIntent.SUCCESS
    if _HESITATION.match(text):
        return StudentIntent.HESITATION
    if _DISENGAGEMENT.search(text):
        return StudentIntent.DISENGAGEMENT
    if _DEPTH_MORE.search(text):
        return StudentIntent.DEPTH_MORE
    if _DEPTH_SHORT.search(text):
        return StudentIntent.DEPTH_SHORT
    if _DEPTH_SIMPLER.search(text):
        return StudentIntent.DEPTH_SIMPLER
    if _ACK.match(text):
        return StudentIntent.ACKNOWLEDGEMENT
    if _HINT.search(text):
        return StudentIntent.HINT
    if _ANSWER_REQUEST.search(text):
        return StudentIntent.ANSWER_REQUEST
    if _CONFUSION.search(text):
        return StudentIntent.CONFUSION
    if _REPEAT.search(text):
        return StudentIntent.REPEAT
    if _UNRELATED.search(text) and not _RELATED.search(text):
        return StudentIntent.UNRELATED
    tell = _TELL_ABOUT.search(text)
    if tell and not _MATH_KEEP.search(tell.group(1)) and not _NAMED_CONCEPT.search(tell.group(1)):
        return StudentIntent.UNRELATED
    if _RELATED.search(text):
        return StudentIntent.RELATED_EDUCATIONAL
    if _TOPIC_CHANGE.search(text):
        return StudentIntent.TOPIC_CHANGE
    if _PRACTICE.search(text):
        return StudentIntent.PRACTICE_REQUEST
    if _DISAGREE.search(text):
        if phase == "practice" and _WEAK_DISAGREE.match(text) and _ANSWER_VALUE.search(text):
            return StudentIntent.STUDENT_ANSWER
        return StudentIntent.DISAGREEMENT
    if _WHY_HOW.search(text):
        return StudentIntent.WHY_HOW
    if phase == "practice" and _STUDENT_ANSWER.search(text):
        return StudentIntent.STUDENT_ANSWER
    if _EXPLAIN.search(text):
        return StudentIntent.EXPLANATION
    if phase == "practice" and len(text.split()) <= 12:
        # Short replies during practice are often attempts — unless clearly a how/solve ask.
        if not _PRACTICE.search(text) and not _EXPLAIN.search(text):
            return StudentIntent.STUDENT_ANSWER
    if "?" in text:
        return StudentIntent.CLARIFICATION
    return StudentIntent.UNKNOWN


def is_help_request(utterance: str) -> bool:
    return bool(_HELP.search(utterance or ""))


def is_simple_factual(utterance: str) -> bool:
    """Short 'what is X' about a local symbol/value, not a named concept."""
    text = (utterance or "").strip()
    if len(text.split()) > 8:
        return False
    if not _SIMPLE_WHAT.search(text):
        return False
    return not _NAMED_CONCEPT.search(text)


def is_interrupt_style(utterance: str) -> bool:
    """New utterance after barge-in — 'Wait, why…' rather than a lone 'wait'."""
    text = (utterance or "").strip()
    if not _INTERRUPT_STYLE.search(text):
        return False
    return not _HESITATION.match(text)


def is_move_on_request(utterance: str) -> bool:
    """True when they want to leave the current problem, not just hear it faster."""
    return bool(_MOVE_ON.search(utterance or ""))
