"""Isolated student-safety layer — intent detection and spoken scripts.

This module is not part of the Tutor Engine. It never calls an LLM. Ordinary
tutoring is a cheap regex miss (typically one scan) and then a no-op.

Detection is meaning-oriented: first-person harm intent, method-seeking, and
the same ideas in Hindi / Hinglish / Tamil / Tanglish / Telugu / Tenglish —
not a single exact English phrase.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from languages import LANG_EN, LANG_HI, LANG_TA, LANG_TE, normalize_session_lang

SafetyCategory = Literal["self_harm", "harm_to_others"]
SafetySeverity = Literal["high"]

EVENT_SAFETY_ALERT = "safety_alert"
SEVERITY_HIGH: SafetySeverity = "high"

# Kept on the LLM context so a later math turn cannot be steered by leftover
# crisis text. Not a tutor-engine prompt.
SAFETY_CONTEXT_MARKER = "[SAFETY_PROTOCOL]"
SAFETY_CONTEXT_NOTE = (
    "[SAFETY_PROTOCOL] A separate safety layer already responded to a student "
    "safety concern. Continue as the Class 10 mathematics tutor. Do not give "
    "instructions about suicide, self-harm, or violence. Do not lecture or "
    "shame. If the student is back on the lesson, teach the math topic "
    "normally and do not bring up the safety topic unless they do."
)


class SafetyPhase(str, Enum):
    IDLE = "idle"
    PAUSED = "paused"


class SafetyKind(str, Enum):
    ALERT = "alert"
    IMMEDIATE_DANGER = "immediate_danger"
    NOT_IN_DANGER = "not_in_danger"
    HOLDING = "holding"
    RESUME = "resume"


# ── Normalisation ────────────────────────────────────────────────────────────

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'"})
# Keep letters (including Indic), marks, digits, apostrophes; drop other punct.
_NON_TOKEN = re.compile(
    r"[^\w\s'\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F]+",
    re.UNICODE,
)
_WS = re.compile(r"\s+", re.UNICODE)

# Common romanisation / spelling collapse so templates fire on natural speech.
_SPELLING = (
    (re.compile(r"\bsucide\b"), "suicide"),
    (re.compile(r"\bsuicid\b"), "suicide"),
    (re.compile(r"\bkms\b"), "kill myself"),
    (re.compile(r"\batmahatya\b"), "aatmahatya"),
    (re.compile(r"\batmhatya\b"), "aatmahatya"),
    (re.compile(r"\bkhudkushi\b"), "khudkhushi"),
    (re.compile(r"\bkhud kushee\b"), "khudkhushi"),
    (re.compile(r"\btharkkolai\b"), "tharkolai"),
    (re.compile(r"\bthatkolai\b"), "tharkolai"),
    (re.compile(r"\bbrathakali\b"), "bathakali"),
    (re.compile(r"\bbatakali\b"), "bathakali"),
    (re.compile(r"\bchavali\b"), "chaavali"),
    (re.compile(r"\bwanna\b"), "want to"),
    (re.compile(r"\bgonna\b"), "going to"),
    (re.compile(r"\bim\b"), "i'm"),
    (re.compile(r"\bdont\b"), "don't"),
    (re.compile(r"\bcant\b"), "can't"),
)


def normalize_utterance(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").translate(_APOSTROPHES)
    value = value.lower().replace("\u200b", "").replace("\ufeff", "")
    value = _NON_TOKEN.sub(" ", value)
    value = _WS.sub(" ", value).strip()
    for pattern, repl in _SPELLING:
        value = pattern.sub(repl, value)
    return value


# ── Fast reject (ordinary tutoring) ──────────────────────────────────────────
# If none of these appear, the utterance cannot be a crisis we handle.

_CRISIS_HINT = re.compile(
    r"("
    r"suicid|self\s*harm|kill(?:ing)?\s+(?:my\s*)?self|hurt(?:ing)?\s+(?:my\s*)?self|"
    r"harm(?:ing)?\s+(?:my\s*)?self|end(?:ing)?\s+(?:my|this)\s+life|"
    r"take(?:ing)?\s+my(?:\s+own)?\s+life|\bdie\b|\bdying\b|\bdead\b|"
    r"murder|hurt\s+some|kill\s+some|hurt\s+(?:him|her|them)|"
    r"kill\s+(?:him|her|them)|don't want to live|do not want to live|"
    r"can't go on|cannot go on|end it all|better off dead|"
    r"not worth living|no (?:point|reason) (?:in|to) liv|"
    r"want to die|going to die|feel like dy|"
    r"आत्महत्या|खुदकुशी|मरना|मरूँ|कैसे मर|मार\s*दू|जीना नहीं|ज़िंदा नहीं|"
    r"खुद को|किसी को मार|हत्या|"
    r"தற்கொலை|சாக|சாவ|கொல்ல|காயப்படுத்த|வாழ\s*விரும்ப|"
    r"ఆత్మహత్య|చావ|చంప|బతక|హింస|"
    r"aatmahatya|khudkhushi|khud ko|marna|marun|mar jaun|mar jaaun|"
    r"jeena nahi|zinda nahi|kisi ko|kaise maar|nuksan|"
    r"tharkolai|saaga|saaganum|vazha virumb|ennai koll|eppadi saag|"
    r"oruthanai koll|kolla poren|yaaraiyaavadhu|kayapadu|"
    r"chaavali|chavalsindi|bathakali|champukovali|ela chava|evvarini champ|"
    r"evarnaina champ|himsin"
    r")",
    re.I | re.UNICODE,
)


# ── Benign idioms (must not fire if a strong crisis construction is also present)

_BENIGN = re.compile(
    r"("
    r"\b(?:phone|battery|laptop|computer|connection|wifi|mic(?:rophone)?|mouse|"
    r"tab|tablet)\s+(?:died|dies|dead)\b|"
    r"\bdie\s+(?:out|down|off)\b|"
    r"\bdying\s+to\s+(?:know|learn|understand|try|see|hear|get)\b|"
    r"\b(?:this|that|it|homework|problem|question|exam|math(?:s)?|chapter|"
    r"topic|work)\s+(?:is\s+)?(?:killing|kills)\s+me\b|"
    r"\bdo\s+or\s+die\b|"
    r"\bnever\s+say\s+die\b|"
    r"\bkill\s+(?:time|the\s+(?:mood|process|variable|term|noise)|two\s+birds)\b|"
    r"\bkiller\s+(?:example|app|feature|problem)\b|"
    r"\bhurt\s+my\s+(?:chances|score|grade|marks|feelings)\b|"
    r"\b(?:what(?:'s| is)|define|definition of|meaning of)\s+suicide\b|"
    r"\bsuicide\s+(?:rate|rates|prevention|hotline)\b|"
    r"\bwho\s+(?:killed|murdered)\b|"
    r"\bhow\s+did\s+\w.+\bdie\b|"
    r"\bdon'?t want to live\s+(?:in|at|there|here|with|on)\b|"
    r"\bdo not want to live\s+(?:in|at|there|here|with|on)\b|"
    r"\bcan(?:not|'t)?\s+go\s+on\s+(?:to|with|from)\b|"
    r"\bin the game\b|\bthe boss\b|\benemy\b"
    r")",
    re.I | re.UNICODE,
)


# ── Harm to others (checked before self-harm so "kill someone" is not self)

_OTHER_OBJECT = (
    r"(?:someone|somebody|some one|a person|people|him|her|them|"
    r"a (?:man|woman|boy|girl|kid|child|friend|classmate|teacher|"
    r"brother|sister)|"
    r"my (?:friend|classmate|teacher|brother|sister|mom|dad|parents)|"
    r"kisi(?:\s+ko)?|kisiko|usko|usko|unhe|"
    r"oruthan(?:ai)?|oruvar(?:ai)?|yaaraiyaavadhu|yaaraiyum|"
    r"evvarini|evarnaina|okkadini|vaadini)"
)

_HARM_OTHERS = re.compile(
    r"("
    # English method-seeking / intent
    r"\bhow\s+(?:to|can i|do i|would i|could i)\s+"
    r"(?:murder|kill|hurt|harm|stab|attack|poison)\s+" + _OTHER_OBJECT + r"\b|"
    r"\b(?:i\s+)?(?:want(?:ing)? to|going to|planning to|plan to|going to)\s+"
    r"(?:murder|kill|hurt|harm|stab|shoot|attack)\s+" + _OTHER_OBJECT + r"\b|"
    r"\bmurder\s+" + _OTHER_OBJECT + r"\b|"
    r"\bi(?:'m| am)?\s+going to (?:hurt|kill|murder|stab)\s+" + _OTHER_OBJECT + r"\b|"
    # Hindi / Hinglish
    r"\bkisi(?:\s+ko)?\s+(?:kaise\s+)?(?:maar|maare|maarna|maar\s+dal|nuksan)|"
    r"\bkaise\s+(?:kisi(?:\s+ko)?|kisiko)\s+maar|"
    r"\bkisiko\s+(?:maar|nuksan)|"
    r"\bmurder\s+kaise|"
    r"किसी\s*को\s*(?:मार|नुकसान|चोट)|"
    r"कैसे\s*(?:किसी\s*को\s*)?मार|"
    r"हत्या\s*कैसे|"
    r"मुझे\s*किसी\s*को\s*(?:मार|नुकसान|चोट)|"
    # Tamil / Tanglish
    r"\b(?:oruthanai|oruvarai|yaaraiyaavadhu|yaaraiyum)\s+"
    r"(?:eppadi\s+)?(?:koll|kolla|kayapadu)|"
    r"\beppadi\s+(?:kollai|kolla|oruthanai)|"
    r"ஒருவ(?:னை|ரை)\s*(?:எப்படி\s*)?(?:கொல்ல|காய)|"
    r"யாரையாவது\s*(?:கொல்ல|காய)|"
    r"(?<!\w)கொலை\s*செய்ய|"
    r"எப்படி\s*கொல்ல|"
    # Telugu / Tenglish
    r"\b(?:evvarini|evarnaina|okkadini)\s+(?:ela\s+)?(?:champ|himsin)|"
    r"\bela\s+champ|"
    r"ఎవరినైనా\s*(?:ఎలా\s*)?(?:చంప|హింస)|"
    r"ఎవరిని\s*(?:చంప|హింస)|"
    r"ఎలా\s*చంప"
    r")",
    re.I | re.UNICODE,
)


# ── Self-harm / suicide intent ───────────────────────────────────────────────

_SELF_HARM = re.compile(
    r"("
    # Desire / ideation / method-seeking (English)
    r"\b(?:i(?:'m| am| have|'ve)?\s+)?(?:feel(?:ing)?(?: like)?|want(?:ing)? to|"
    r"going to|thinking (?:of|about)|thoughts? (?:of|about)|planning to|plan to)\s+"
    r"(?:commit(?:ting)?\s+)?suicid|"
    r"\b(?:commit(?:ting)?|attempt(?:ing)?)\s+suicid|"
    r"\bi\s+feel\s+suicid|"
    r"\bkill(?:ing)?\s+(?:my\s*)?self\b|"
    r"\bhurt(?:ing)?\s+(?:my\s*)?self\b|"
    r"\bharm(?:ing)?\s+(?:my\s*)?self\b|"
    r"\bcut(?:ting)?\s+(?:my\s*)?self\b|"
    r"\bend(?:ing)?\s+(?:my(?: own)? |this )?life\b|"
    r"\btake(?:ing)?\s+my(?: own)? life\b|"
    r"\b(?:want to|going to|wish (?:i could |to )?|feel(?:ing)? like)\s+die\b|"
    r"\bi wish i (?:was|were) dead\b|"
    r"\bbetter off dead\b|"
    r"\bno(?:t)? (?:point|reason) (?:in|to) (?:liv(?:e|ing)|being alive)\b|"
    r"\b(?:life|living) (?:is )?not worth (?:it|living)\b|"
    r"\bhow (?:can|do|would|could) i (?:even )?(?:die|end it|kill myself|end my life)\b|"
    r"\bhow to (?:die|kill myself|commit suicide|end my life)\b|"
    r"\b(?:easiest|painless|best) way to (?:die|kill myself)\b|"
    r"\bend it all\b|"
    r"\bdon'?t want to (?:live|be alive|exist)(?!\s+(?:in|at|there|here|with|on)\b)|"
    r"\bdo not want to (?:live|be alive|exist)(?!\s+(?:in|at|there|here|with|on)\b)|"
    r"\bi (?:just )?can't go on(?:\s+(?:anymore|any more|any longer))?(?!\s+(?:to|with|from)\b)|"
    r"\bi cannot go on(?:\s+(?:anymore|any more|any longer))?(?!\s+(?:to|with|from)\b)|"
    r"\btired of (?:living|being alive)\b|"
    r"\bself[-\s]?harm\b|"
    r"\bi (?:want to|going to) kill\s*$|"
    # Hindi / Hinglish
    r"\baatmahatya|"
    r"\bkhudkhushi|"
    r"\b(?:main|mai|mujhe|mujhko)\s+(?:marna|mar ja|suicide)|"
    r"\bmarna\s+(?:hai|chahta|chahti)|"
    r"\b(?:jeena|jeene)\s+nahi|"
    r"\bzinda\s+nahi|"
    r"\bkhud ko\s+(?:maar|nuksan|hurt|cut)|"
    r"\bkaise\s+(?:marun|maru|mar jaaun|mar jaun)|"
    r"आत्महत्या|"
    r"खुदकुशी|खुदकुशी|"
    r"(?:मैं|मुझे)\s*(?:मरना|मार\s*दू|आत्महत्या|सुसाइड)|"
    r"जीना\s*नहीं|"
    r"ज़िंदा\s*नहीं|जिंदा\s*नहीं|"
    r"खुद\s*को\s*(?:मार|नुकसान|चोट)|"
    r"कैसे\s*मर|"
    r"अब\s*(?:और\s*)?नहीं\s*(?:सह|हो)\s*सक|"
    # Tamil / Tanglish
    r"\btharkolai|"
    r"\b(?:naan|naa|enakku)\s+(?:saaga|saaganum|saaga poren)|"
    r"\bsaaga\s+(?:virumbu|poren|num)|"
    r"\bvazha\s+(?:virumbala|mudiyala|vendaam)|"
    r"\bennai\s+(?:koll|kayapadu|thinna)|"
    r"\beppadi\s+saag|"
    r"தற்கொலை|"
    r"(?:நான்|எனக்கு)\s*(?:சாக|சாவ)|"
    r"சாக\s*(?:விரும்பு|போற|ணும்)|"
    r"வாழ\s*(?:விரும்பல|முடியல|வேண்டாம்)|"
    r"என்னை\s*(?:கொல்ல|காயப்படுத்த)|"
    r"எப்படி\s*சாக|"
    r"இனி\s*வாழ\s*முடிய|"
    # Telugu / Tenglish
    r"\baatmahatya|"
    r"\b(?:nenu|naku)\s+(?:chaavali|chaavaalani|chavalsindi)|"
    r"\bchaavali|"
    r"\bbathakali\s+(?:ledu|anipiyyatledu|anukovatledu)|"
    r"\bnannu\s+(?:champukovali|himsinchukovali)|"
    r"\bela\s+chava|"
    r"ఆత్మహత్య|"
    r"(?:నేను|నాకు)\s*(?:చావాలి|చావాలని|చావాల)|"
    r"చావాలనుకుంట|"
    r"బతకాలని\s*లేదు|బతకలే|"
    r"నన్ను\s*(?:చంపుకో|హింసించుకో)|"
    r"ఎలా\s*చావ|"
    r"ఇక\s*బతకలే"
    r")",
    re.I | re.UNICODE,
)


# Strong constructions that override a benign idiom in the same utterance.
_STRONG_CRISIS = re.compile(
    r"("
    r"suicid|kill(?:ing)?\s+(?:my\s*)?self|hurt(?:ing)?\s+(?:my\s*)?self|"
    r"want to die|don'?t want to live(?!\s+(?:in|at|there|here|with|on)\b)|"
    r"aatmahatya|khudkhushi|आत्महत्या|"
    r"தற்கொலை|ఆత్మహత్య|murder\s+(?:someone|somebody)|kill\s+someone"
    r")",
    re.I | re.UNICODE,
)


_RESUME = re.compile(
    r"("
    r"\b(?:let'?s\s+)?(?:continue|study)\b|"
    r"\bback to (?:the )?(?:lesson|math|chapter|question|problem)\b|"
    r"\b(?:explain|substitution|equation|algebra|linear|quadratic|polynomial|"
    r"solve|example|exercise|homework|theorem|formula|factori[sz]e|"
    r"next (?:question|problem|step|example)|chapter|practi[cs]e)\b|"
    r"समीकरण|अध्याय|सवाल|"
    r"சமன்பாடு|பாடம்|"
    r"సమీకరణం|పాఠం"
    r")",
    re.I | re.UNICODE,
)

_IMMEDIATE_DANGER = re.compile(
    r"("
    r"^\s*(?:yes|yeah|yep|yup|yea)\b|"
    r"\bright now\b|\bjust now\b|\btonight\b|\bthis (?:night|evening)\b|"
    r"\bi(?:'m| am) in (?:danger|trouble)\b|"
    r"\bi have a plan\b|"
    r"\bi have (?:the )?(?:pills|a knife|a blade|razor|poison)\b|"
    r"\bgoing to (?:do it|kill myself|hurt myself)\b|"
    r"^\s*haan+\b|"
    r"\babhi(?:\s+(?:hi|khatra|danger))?\b|"
    r"^\s*(?:हाँ|हां)\b|अभी\s*(?:खतरा|है)|"
    r"^\s*(?:ஆம்|ஆமாம்)\b|இப்போதே|"
    r"^\s*అవును\b|ఇప్పుడే"
    r")",
    re.I | re.UNICODE,
)

_NOT_IN_DANGER = re.compile(
    r"("
    r"^\s*(?:no|nope|nah|not really)\b|"
    r"\bi(?:'m| am) (?:ok|okay|fine|safe|alright|not in danger)\b|"
    r"\bnot in (?:any )?danger\b|"
    r"^\s*(?:nahi|nahin|illa|ledu)\b|"
    r"^\s*(?:नहीं|ना)\b|"
    r"^\s*(?:இல்ல|இல்லை)\b|"
    r"^\s*లేదు\b"
    r")",
    re.I | re.UNICODE,
)


@dataclass(frozen=True)
class SafetyHit:
    category: SafetyCategory
    severity: SafetySeverity = SEVERITY_HIGH


@dataclass
class SafetyTurnResult:
    kind: SafetyKind
    swallow: bool
    drop_last_user: bool
    spoken: str
    event: dict[str, Any] | None
    force_speak: bool = True


def classify(text: str) -> SafetyHit | None:
    """Return a high-risk hit, or None for ordinary tutoring.

    Ordinary turns exit after one hint scan when no crisis-related tokens
    appear — effectively zero added latency on the voice path.
    """
    normalized = normalize_utterance(text)
    if not normalized or not _CRISIS_HINT.search(normalized):
        return None
    if _BENIGN.search(normalized) and not _STRONG_CRISIS.search(normalized):
        return None
    # Suicide / self-harm first so words like தற்கொலை (which contains கொலை)
    # are not classified as harm-to-others.
    if _SELF_HARM.search(normalized):
        return SafetyHit("self_harm")
    if _HARM_OTHERS.search(normalized):
        return SafetyHit("harm_to_others")
    return None


def is_resume_utterance(text: str) -> bool:
    normalized = normalize_utterance(text)
    return bool(normalized and _RESUME.search(normalized))


def is_immediate_danger_utterance(text: str) -> bool:
    normalized = normalize_utterance(text)
    return bool(normalized and _IMMEDIATE_DANGER.search(normalized))


def is_not_in_danger_utterance(text: str) -> bool:
    normalized = normalize_utterance(text)
    return bool(normalized and _NOT_IN_DANGER.search(normalized))


# ── Spoken scripts (active session language; no method instructions) ─────────

_SELF_HARM_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "I'm really sorry you're feeling this way. I'm glad you told me. "
        "Your life matters, and hurting yourself isn't the answer. "
        "Please talk to someone you trust—a parent, teacher, or another adult—"
        "and don't stay alone with these feelings. "
        "Are you in immediate danger right now?"
    ),
    LANG_HI: (
        "मुझे बहुत अफ़सोस है कि तुम ऐसा महसूस कर रहे हो। अच्छा है कि तुमने बताया। "
        "तुम्हारी ज़िंदगी मायने रखती है, और खुद को नुकसान पहुँचाना कोई हल नहीं है। "
        "कृपया किसी भरोसेमंद व्यक्ति से बात करो—माँ-बाप, टीचर, या कोई और बड़े। "
        "इन भावनाओं के साथ अकेले मत रहो। क्या तुम्हें अभी कोई खतरा है?"
    ),
    LANG_TA: (
        "நீ இப்படி உணர்வது எனக்கு மிகவும் வருத்தமாக இருக்கிறது. நீ சொன்னது நல்லது. "
        "உன் உயிர் முக்கியம், உன்னை நீயே காயப்படுத்துவது தீர்வு அல்ல. "
        "நம்பகமான ஒருவரிடம் பேசு—பெற்றோர், ஆசிரியர், அல்லது வேறு ஒரு பெரியவர். "
        "இந்த உணர்வுகளுடன் தனியாக இருக்காதே. இப்போது உனக்கு உடனடி ஆபத்து இருக்கிறதா?"
    ),
    LANG_TE: (
        "నువ్వు ఇలా అనుకోవడం నాకు చాలా బాధగా ఉంది. చెప్పినందుకు నేను సంతోషిస్తున్నాను. "
        "నీ ప్రాణం విలువైనది, నిన్ను నువ్వు హాని చేసుకోవడం సమాధానం కాదు. "
        "నమ్మకమైన వాళ్లతో మాట్లాడు—తల్లిదండ్రులు, టీచర్, లేదా ఇంకొక పెద్దవారు. "
        "ఈ భావాలతో ఒంటరిగా ఉండకు. ఇప్పుడు నీకు తక్షణ ప్రమాదం ఉందా?"
    ),
}

_HARM_OTHERS_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "I can't help with hurting someone. If you're feeling like you might "
        "act on this, please step away from the situation and get a trusted "
        "adult or emergency help involved."
    ),
    LANG_HI: (
        "मैं किसी को चोट पहुँचाने में मदद नहीं कर सकती। अगर तुम्हें लग रहा है कि "
        "तुम कुछ कर सकते हो, तो उस स्थिति से हट जाओ और किसी भरोसेमंद बड़े या "
        "आपातकालीन मदद को शामिल करो।"
    ),
    LANG_TA: (
        "யாரையும் காயப்படுத்துவதில் என்னால் உதவ முடியாது. நீ இதைச் செய்யலாம் என்று "
        "தோன்றினால், அந்த சூழலிலிருந்து விலகி, நம்பகமான பெரியவர் அல்லது அவசர "
        "உதவியை அணுகு."
    ),
    LANG_TE: (
        "ఎవరినైనా బాధపెట్టడంలో నేను సహాయం చేయను. ఇలా చేస్తానని అనిపిస్తే, ఆ "
        "పరిస్థితి నుంచి తప్పుకుని నమ్మకమైన పెద్దవారిని లేదా అత్యవసర సహాయాన్ని "
        "పాలుపంచు."
    ),
}

_IMMEDIATE_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "If you are in danger right now, please get help immediately. "
        "Tell a parent, teacher, or another adult near you, or contact "
        "emergency services. In India you can call Tele-MANAS at 1 4 4 1 6 — "
        "that's available 24 hours. You don't have to handle this alone."
    ),
    LANG_HI: (
        "अगर तुम्हें अभी खतरा है, तो तुरंत मदद लो। किसी अभिभावक, टीचर, या पास के "
        "बड़े से कहो, या आपातकालीन सेवा से संपर्क करो। भारत में Tele-MANAS "
        "1 4 4 1 6 पर चौबीसों घंटे बात कर सकते हो। तुम्हें अकेले नहीं निपटना है।"
    ),
    LANG_TA: (
        "இப்போது ஆபத்து இருந்தால் உடனே உதவி வாங்கு. பெற்றோர், ஆசிரியர், அல்லது "
        "அருகில் இருக்கும் பெரியவரிடம் சொல், அல்லது அவசர சேவையை அணுகு. இந்தியாவில் "
        "Tele-MANAS 1 4 4 1 6 இல் 24 மணி நேரமும் உதவி கிடைக்கும். இதை தனியாக "
        "சமாளிக்க வேண்டாம்."
    ),
    LANG_TE: (
        "ఇప్పుడు ప్రమాదం ఉంటే వెంటనే సహాయం తీసుకో. తల్లిదండ్రులు, టీచర్, లేదా "
        "దగ్గర ఉన్న పెద్దవారితో చెప్పు, లేదా అత్యవసర సేవలను కలుపు. భారతదేశంలో "
        "Tele-MANAS 1 4 4 1 6కి రోజంతా సహాయం ఉంటుంది. దీన్ని ఒంటరిగా ఎదుర్కోవద్దు."
    ),
}

_HOLDING_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "I'm here with you. Please talk to a trusted adult. When you're ready, "
        "we can go back to the lesson."
    ),
    LANG_HI: (
        "मैं तुम्हारे साथ हूँ। कृपया किसी भरोसेमंद बड़े से बात करो। जब तुम तैयार "
        "हो, हम पाठ पर वापस जा सकते हैं।"
    ),
    LANG_TA: (
        "நான் உன்னுடன் இருக்கிறேன். நம்பகமான ஒரு பெரியவரிடம் பேசு. நீ தயாரானதும் "
        "பாடத்திற்குத் திரும்பலாம்."
    ),
    LANG_TE: (
        "నేను నీతో ఉన్నాను. దయచేసి నమ్మకమైన పెద్దవారితో మాట్లాడు. నువ్వు సిద్ధమైతే "
        "పాఠానికి తిరిగి వెళ్దాం."
    ),
}

_SAFE_NOW_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "I'm glad you're safe right now. Please still talk to someone you "
        "trust—a parent, teacher, or another adult. When you're ready, we can "
        "go back to the lesson."
    ),
    LANG_HI: (
        "अच्छा है कि तुम अभी सुरक्षित हो। फिर भी किसी भरोसेमंद व्यक्ति से बात "
        "करो—माँ-बाप, टीचर, या कोई और बड़े। जब तुम तैयार हो, हम पाठ पर वापस जा "
        "सकते हैं।"
    ),
    LANG_TA: (
        "இப்போது நீ பாதுகாப்பாக இருப்பது நல்லது. இருந்தாலும் நம்பகமான ஒருவரிடம் "
        "பேசு—பெற்றோர், ஆசிரியர், அல்லது வேறு ஒரு பெரியவர். நீ தயாரானதும் "
        "பாடத்திற்குத் திரும்பலாம்."
    ),
    LANG_TE: (
        "ఇప్పుడు నువ్వు సురక్షితంగా ఉండటం ఆనందంగా ఉంది. అయినా నమ్మకమైన వాళ్లతో "
        "మాట్లాడు—తల్లిదండ్రులు, టీచర్, లేదా ఇంకొక పెద్దవారు. నువ్వు సిద్ధమైతే "
        "పాఠానికి తిరిగి వెళ్దాం."
    ),
}

_OTHERS_URGENT_SCRIPTS: dict[str, str] = {
    LANG_EN: (
        "Please stop and get a trusted adult or emergency help involved right "
        "now. Do not hurt anyone. If someone is in danger, call emergency "
        "services immediately."
    ),
    LANG_HI: (
        "कृपया रुक जाओ और अभी किसी भरोसेमंद बड़े या आपातकालीन मदद को शामिल करो। "
        "किसी को चोट मत पहुँचाओ। अगर किसी को खतरा है, तो तुरंत आपातकालीन सेवा "
        "को कॉल करो।"
    ),
    LANG_TA: (
        "தயவுசெய்து நில், இப்போதே நம்பகமான பெரியவர் அல்லது அவசர உதவியை அணுகு. "
        "யாரையும் காயப்படுத்தாதே. யாருக்காவது ஆபத்து இருந்தால் உடனே அவசர சேவையை "
        "அழை."
    ),
    LANG_TE: (
        "దయచేసి ఆపు, ఇప్పుడే నమ్మకమైన పెద్దవారిని లేదా అత్యవసర సహాయాన్ని "
        "పాలుపంచు. ఎవరినీ బాధపెట్టవద్దు. ఎవరికైనా ప్రమాదం ఉంటే వెంటనే అత్యవసర "
        "సేవలను కలుపు."
    ),
}


def _lang(code: str | None) -> str:
    return normalize_session_lang(code) or LANG_EN


def spoken_self_harm(language: str | None) -> str:
    return _SELF_HARM_SCRIPTS[_lang(language)]


def spoken_harm_to_others(language: str | None) -> str:
    return _HARM_OTHERS_SCRIPTS[_lang(language)]


def spoken_immediate_danger(language: str | None) -> str:
    return _IMMEDIATE_SCRIPTS[_lang(language)]


def spoken_holding(language: str | None) -> str:
    return _HOLDING_SCRIPTS[_lang(language)]


def spoken_not_in_danger(language: str | None) -> str:
    return _SAFE_NOW_SCRIPTS[_lang(language)]


def spoken_harm_others_urgent(language: str | None) -> str:
    return _OTHERS_URGENT_SCRIPTS[_lang(language)]


def spoken_for(category: SafetyCategory, language: str | None) -> str:
    if category == "harm_to_others":
        return spoken_harm_to_others(language)
    return spoken_self_harm(language)


def make_alert_event(
    category: SafetyCategory,
    now: float,
    *,
    spoken: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": EVENT_SAFETY_ALERT,
        "category": category,
        "severity": SEVERITY_HIGH,
        "timestamp": int(now * 1000),
    }
    if spoken:
        event["spoken"] = spoken
    return event


class SafetyStore:
    """Per-session pause state. Classification itself is stateless."""

    def __init__(self) -> None:
        self.phase: SafetyPhase = SafetyPhase.IDLE
        self.last_category: SafetyCategory | None = None
        self.awaiting_danger_reply: bool = False

    @property
    def paused(self) -> bool:
        return self.phase == SafetyPhase.PAUSED

    def reset(self) -> None:
        self.phase = SafetyPhase.IDLE
        self.last_category = None
        self.awaiting_danger_reply = False

    def apply(
        self,
        utterance: str,
        *,
        language: str,
        now: float,
    ) -> SafetyTurnResult | None:
        hit = classify(utterance)
        if hit is not None:
            return self._alert(hit, language, now)

        if self.phase == SafetyPhase.IDLE:
            return None

        if is_resume_utterance(utterance):
            self.phase = SafetyPhase.IDLE
            self.awaiting_danger_reply = False
            return SafetyTurnResult(
                kind=SafetyKind.RESUME,
                swallow=False,
                drop_last_user=False,
                spoken="",
                event=None,
            )

        if (
            self.awaiting_danger_reply
            and is_immediate_danger_utterance(utterance)
        ):
            spoken = spoken_immediate_danger(language)
            self.awaiting_danger_reply = False
            category = self.last_category or "self_harm"
            return SafetyTurnResult(
                kind=SafetyKind.IMMEDIATE_DANGER,
                swallow=True,
                drop_last_user=True,
                spoken=spoken,
                event=make_alert_event(category, now, spoken=spoken),
            )

        if (
            self.last_category == "harm_to_others"
            and is_immediate_danger_utterance(utterance)
            and not is_not_in_danger_utterance(utterance)
        ):
            spoken = spoken_harm_others_urgent(language)
            return SafetyTurnResult(
                kind=SafetyKind.IMMEDIATE_DANGER,
                swallow=True,
                drop_last_user=True,
                spoken=spoken,
                event=make_alert_event("harm_to_others", now, spoken=spoken),
            )

        if is_not_in_danger_utterance(utterance):
            spoken = spoken_not_in_danger(language)
            self.awaiting_danger_reply = False
            return SafetyTurnResult(
                kind=SafetyKind.NOT_IN_DANGER,
                swallow=True,
                drop_last_user=True,
                spoken=spoken,
                event=None,
            )

        spoken = spoken_holding(language)
        return SafetyTurnResult(
            kind=SafetyKind.HOLDING,
            swallow=True,
            drop_last_user=True,
            spoken=spoken,
            event=None,
        )

    def _alert(
        self,
        hit: SafetyHit,
        language: str,
        now: float,
    ) -> SafetyTurnResult:
        self.phase = SafetyPhase.PAUSED
        self.last_category = hit.category
        self.awaiting_danger_reply = hit.category == "self_harm"
        spoken = spoken_for(hit.category, language)
        return SafetyTurnResult(
            kind=SafetyKind.ALERT,
            swallow=True,
            drop_last_user=True,
            spoken=spoken,
            event=make_alert_event(hit.category, now, spoken=spoken),
        )
