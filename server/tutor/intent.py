"""Deterministic student-intent heuristics — no extra LLM call."""

# Intent only routes the turn. Spoken action is chosen in tutor.steer.
from __future__ import annotations

import re

from tutor.steer import SITUATION_NEEDS, classify_need, soften_student_text
from tutor.types import StudentIntent

_CONFUSION = re.compile(
    r"("
    r"\bi\s+(?:still\s+)?don'?t understand\b|"
    r"\bdont understand\b|"
    r"\bdon'?t get it\b|"
    r"\bstill don'?t get\b|"
    r"\bconfused\b|\bconfusing\b|"
    r"\bi'?m lost\b|"
    r"\bnot getting\b|"
    r"\bdoesn'?t make sense\b|"
    r"\btoo (?:hard|difficult)\b|"
    r"\bthis is (?:too )?(?:hard|difficult|confusing)\b|"
    r"\bhard to (?:understand|follow|get)\b|"
    # Roman Hinglish struggle signals
    r"\bsamajh (?:nahi|nahin|me nahi|mein nahi)\b|"
    r"\b(?:bahut|bohot|thoda) mushkil\b|\bmushkil hai\b|"
    r"\bkathin hai\b|\bconfusing hai\b|"
    # Roman Tanglish struggle signals
    r"\bpuriyala\b|\bpuriyathu\b|\bpuriyala illa\b|"
    r"\b(?:idhu|ithu|adhu) kashtam\b|\bkashtama irukku\b|\bkadinam(?:aana)?\b|"
    # Roman Tenglish struggle signals
    r"\bartham (?:kavatledu|kaledu|kaadu)\b|"
    r"\b(?:chala|chaala) kashtam(?:ga)?\b|\bkashtamga undi\b|"
    # Native scripts
    r"समझ नहीं|मुश्किल है|कठिन है|"
    r"புரியல|கஷ்டம்|கடினம்|"
    r"అర్థం (?:కాలేదు|కావట్లేదు)|కష్టం(?:గా)?"
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
    r"politics|election|"
    r"prime minister|chief minister|governor of|mayor of|"
    r"cm of|pm of|president of|mla of|cabinet minister|"
    r"news|shopping|amazon|weather|forecast|"
    r"joke|instagram|tiktok|youtube(?: channel)?|"
    r"bitcoin|stock market|match score|"
    r"capital of|who won|who is the (?:cm|pm|president|governor|mayor|prime minister|chief minister)|"
    r"forget (?:the )?(?:maths?|math|lesson|chapter|topic)|"
    r"something (?:else|different|unrelated|random)|"
    r"anything (?:else|other)|"
    r"random (?:topic|question|thing)"
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
    r"\b(?:don'?t|do not) want to study\b|"
    r"\b(?:don'?t|do not) (?:want|wanna) to (?:do|continue|keep doing|study) (?:this|it|maths?|math)?\b|"
    r"\bdon'?t feel like (?:studying|this|doing this)\b|"
    r"\b(?:not interested|i hate this|tired of this|had enough)\b|"
    r"\b(?:let'?s skip|skip (?:this|it)|move on)\b|"
    r"बोर|ऊब|मन नहीं लग|"
    r"சலிப்பு"
    r")",
    re.I,
)

_MOVE_ON = re.compile(
    r"("
    r"\b(?:don'?t|do not) want to study\b|"
    r"\b(?:skip (?:this|it)|let'?s skip|move on|enough (?:of this|for now))\b|"
    r"\b(?:don'?t|do not) (?:want|wanna) to (?:do|continue|keep doing|study) (?:this|it|maths?|math)?\b"
    r")",
    re.I,
)

# First-person need/state that is not a maths ask — the LLM infers the situation.
_SITUATION = re.compile(
    r"("
    r"\bi(?:'?m| am)\s+(?:really |so |pretty |kinda |kind of )?"
    r"(?:tired|exhausted|hungry|starving|sleepy|wiped|drained)\b|"
    r"\bi haven'?t eaten\b|"
    r"\bmy (?:brain|head) (?:is )?(?:completely |totally |so )?(?:done|fried|full|tired)\b|"
    r"\bmy (?:stomach|tummy|belly)\b|"
    r"\bi want to eat\b|"
    r"\b(?:can|could) (?:i|we) (?:eat|stop|pause|go|rest|grab|take)\b|"
    r"\b(?:take|need) a break\b|"
    r"\bi (?:have to|need to|gotta|got to) (?:go|leave)\b|"
    r"\b(?:friends? are|friend is) (?:calling|texting|waiting)\b|"
    r"\bi (?:want|wanna|need|feel like)(?: to)? (?!"
    r".*\b(?:hint|example|explain|understand|solve|practice|try|learn)\b)"
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

_SMALL_TALK = re.compile(
    r"^\s*(how are you(?: doing)?(?: today)?|how(?:'re| are) you|"
    r"what'?s up|wassup|sup)\s*[.?!]?\s*$",
    re.I,
)

_TRANSITION_CONFIRM = re.compile(
    r"^\s*(?:yes|yep|yeah|sure|ok(?:ay)?|alright|ready)"
    r"(?:\s+ready)?\s*[.!]?\s*$",
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
    r"i got a different answer|i think that'?s wrong|your answer is wrong"
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
    r"("
    r"\bdifferent (?:topic|subject|chapter)\b|"
    r"\banother (?:chapter|subject|topic)\b|"
    r"\bsome other (?:topic|subject|chapter)\b|"
    r"\bskip (?:this|to|it)\b|"
    r"\blet'?s (?:do|move to|switch to|talk about)\b|"
    r"\bchange (?:the )?(?:topic|subject|chapter)\b|"
    r"\bswitch (?:the )?(?:topic|subject|chapter)\b|"
    r"\bshift (?:the )?(?:topic|subject|chapter)\b|"
    r"\bdeviate(?:\s+(?:from|the))?(?:\s+(?:topic|subject|chapter|lesson))?\b|"
    r"\bnext chapter\b|"
    r"\bcan we (?:talk|discuss|do) (?:about )?(?:something|anything) (?:else|different|other)\b"
    r")",
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
    text = soften_student_text(utterance)
    if not text:
        return StudentIntent.UNKNOWN

    if _GREETING.search(text) and len(text) < 40:
        return StudentIntent.GREETING
    if _SMALL_TALK.match(text):
        return StudentIntent.GREETING
    if _HELP.search(text):
        return StudentIntent.EXPLANATION
    if _SUCCESS.search(text):
        return StudentIntent.SUCCESS
    if _HESITATION.match(text):
        return StudentIntent.HESITATION
    if _DISENGAGEMENT.search(text):
        return StudentIntent.DISENGAGEMENT
    if is_strong_ready(text):
        return StudentIntent.EXPLANATION
    if _TRANSITION_CONFIRM.match(text):
        return StudentIntent.ACKNOWLEDGEMENT
    if _SITUATION.search(text):
        return StudentIntent.UNRELATED
    if classify_need(text) in SITUATION_NEEDS:
        return StudentIntent.UNRELATED
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


class CheckInReason:
    BORED = "bored"
    CONFUSED = "confused"
    UNCLEAR = "unclear"
    NONE = "none"


_CHECK_IN_BORED = re.compile(
    r"\b(bor(?:ed|ing)|tedious|dull|not interesting)\b",
    re.I,
)
_CHECK_IN_CONFUSED = re.compile(
    r"\b("
    r"confus\w*|hard(?:er)?|difficult|lost|stuck|"
    r"don'?t get|dont get|can'?t follow|cannot follow|"
    r"hard to follow|not clicking|didn'?t click"
    r")\b",
    re.I,
)
_DISMISSIVE = re.compile(
    r"("
    r"\b(?:shut\s*up|shutup|stfu|be quiet)\b|"
    r"^\s*stop(?:\s+it)?\s*[.!]?\s*$|"
    r"^\s*(?:whatever|idc|don'?t care|dont care)\s*[.!]?\s*$"
    r")",
    re.I,
)
_DONE_NOW = re.compile(
    r"\b("
    r"stop(?: here| now)?|done|enough|leave|go|"
    r"that(?:'s| is) (?:it|enough)|"
    r"i(?:'?m| am) done"
    r")\b",
    re.I,
)
_UNCLEAR_REASON = re.compile(
    r"^\s*(ok(?:ay)?|yeah|yes|yep|the (?:first|second|third)|all|both)\s*[.!]?\s*$",
    re.I,
)


def classify_check_in_reason(utterance: str) -> str:
    """Why they said the topic is not working, after a check-in. Not an intent."""
    text = soften_student_text(utterance)
    bored = bool(_CHECK_IN_BORED.search(text))
    confused = bool(_CHECK_IN_CONFUSED.search(text))
    if bored and confused:
        return CheckInReason.CONFUSED
    if bored:
        return CheckInReason.BORED
    if confused:
        return CheckInReason.CONFUSED
    if _UNCLEAR_REASON.match(text):
        return CheckInReason.UNCLEAR
    return CheckInReason.NONE


def is_dismissive(utterance: str) -> bool:
    """Curt pushback after a re-engage — not a maths ask, not a rest need."""
    return bool(_DISMISSIVE.search(soften_student_text(utterance)))


def is_done_now(utterance: str) -> bool:
    """They confirmed they want to stop the session."""
    return bool(_DONE_NOW.search(soften_student_text(utterance)))


_POST_CORRECTION_FRUSTRATION = re.compile(
    r"("
    r"\b(?:shit|crap|fuck|fucking|stupid|dumb|sucks|hate|useless)\b|"
    r"\bthis is (?:shit|crap|dumb|stupid|useless)\b|"
    r"\b(?:i\s+)?d(?:on'?t|ont) know\b|"
    r"\bidk\b|"
    r"\bi give up\b"
    r")",
    re.I,
)


def is_post_correction_frustration(utterance: str, intent: StudentIntent) -> bool:
    """Disengagement or heat right after a wrong-answer correction."""
    if intent in {StudentIntent.DISENGAGEMENT, StudentIntent.CONFUSION}:
        return True
    text = soften_student_text(utterance)
    if is_dismissive(text):
        return True
    if classify_check_in_reason(text) in {CheckInReason.BORED, CheckInReason.CONFUSED}:
        return True
    return bool(_POST_CORRECTION_FRUSTRATION.search(text))


_GIVE_UP = re.compile(
    r"("
    r"\b(?:i\s+)?d(?:on'?t|ont) know\b|"
    r"\bidk\b|"
    r"\bi give up\b|"
    r"\bno (?:idea|clue)\b|"
    r"\bi can'?t do (?:it|this)\b|"
    r"\b(?:forget it|whatever,? i give up)\b"
    r")",
    re.I,
)


def is_give_up(utterance: str) -> bool:
    """Explicit low-bandwidth surrender, with or without frustration."""
    return bool(_GIVE_UP.search(soften_student_text(utterance)))


_HOSTILE_TO_TUTOR = re.compile(
    r"("
    r"\b(?:shut\s*(?:the\s+fuck\s+)?up|stfu)\b|"
    r"\bfuck\s+(?:you|u|off|off\s+u)\b|"
    r"\bf\*+\s*(?:you|u|off)\b|"
    r"\byou(?:'re|\s+are)\s+(?:so\s+|really\s+|such\s+)?"
    r"(?:stupid|dumb|useless|trash|garbage|shit|"
    r"an?\s+(?:idiot|moron|fool|loser)|the\s+worst)\b|"
    r"\byou\s+(?:suck|are\s+bad|are\s+trash|know\s+nothing)\b|"
    r"\b(?:stupid|dumb|useless|shitty|trash|garbage|worthless)\s+"
    r"(?:tutor|ai|bot|teacher|assistant)\b|"
    r"\bshut\s+it\b|"
    r"\bwhat the (?:fuck|hell)\b.{0,80}\byou\b|"
    r"\bwhy are you\b.{0,60}\b(?:fuck|fucking|desperately)\b"
    r")",
    re.I,
)


def is_hostile_to_tutor(utterance: str) -> bool:
    """Insult or profanity aimed at the tutor, not just frustration with the topic."""
    return bool(_HOSTILE_TO_TUTOR.search(soften_student_text(utterance)))


_READY_STRONG = re.compile(
    r"("
    r"\b(?:let'?s|lets)\s+(?:get going|go|start|begin|continue|do this|do it)\b|"
    r"\b(?:no questions?|no question)\b|"
    r"\b(?:get going|go ahead|carry on)\b|"
    r"\bi(?:'?m| am) ready\b|"
    r"\bready to (?:start|go|begin|continue)\b|"
    r"^\s*(?:continue|start|begin)\s*[.!]?\s*$|"
    r"\b(?:continue|start) (?:the )?(?:lesson|class|topic)\b"
    r")",
    re.I,
)
_READY_WEAK = re.compile(
    r"^\s*(ok(?:ay)?|yeah|yes|yep|sure|alright|right|cool)\s*[.!]?\s*$",
    re.I,
)
_MISSED_TURN = re.compile(
    r"("
    r"\bwhy (?:no|didn'?t you|did not you) (?:reply|respond|answer)\b|"
    r"\bno reply\b|"
    r"\byou (?:didn'?t|did not|never) (?:reply|respond|answer)\b|"
    r"\bi (?:already |just )?asked\b|"
    r"\bare you (?:there|here)\b|"
    r"\byou ignored\b|"
    r"\bdidn'?t come through\b"
    r")",
    re.I,
)


def is_strong_ready(utterance: str) -> bool:
    """Explicit 'let's continue / I'm ready' — not a struggle signal."""
    return bool(_READY_STRONG.search(soften_student_text(utterance)))


def is_ready_to_proceed(utterance: str) -> bool:
    """Neutral or positive continue/ready signal. When in doubt, this wins."""
    text = soften_student_text(utterance)
    return bool(_READY_STRONG.search(text) or _READY_WEAK.match(text))


def is_transition_confirm(utterance: str) -> bool:
    """Yes/sure after a 'ready for the next slide?' offer — not a backchannel okay."""
    return bool(_TRANSITION_CONFIRM.match(soften_student_text(utterance)))


def is_missed_turn(utterance: str) -> bool:
    """They noticed a skipped, missing, or unanswered prior turn."""
    return bool(_MISSED_TURN.search(soften_student_text(utterance)))
