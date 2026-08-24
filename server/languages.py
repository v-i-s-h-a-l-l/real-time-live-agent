"""Language helpers for Lumina multilingual voice (en / hi / ta / te)."""

from __future__ import annotations

import re

from pipecat.transcriptions.language import Language

# Session codes used across the app
LANG_EN = "en-IN"
LANG_HI = "hi-IN"
LANG_TA = "ta-IN"
LANG_TE = "te-IN"

SUPPORTED_LANGUAGES: tuple[str, ...] = (LANG_EN, LANG_HI, LANG_TA, LANG_TE)

# Indian regional languages the tutor speaks natively (i.e. not English).
INDIC_LANGUAGES: frozenset[str] = frozenset({LANG_HI, LANG_TA, LANG_TE})

# How the student is writing — Roman Hinglish/Tanglish vs native letters.
SCRIPT_ROMAN = "roman"
SCRIPT_NATIVE = "native"

DISPLAY_NAMES = {
    LANG_EN: "English",
    LANG_HI: "Hindi",
    LANG_TA: "Tamil",
    LANG_TE: "Telugu",
}

# Unicode script ranges
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_TAMIL = re.compile(r"[\u0B80-\u0BFF]")
_TELUGU = re.compile(r"[\u0C00-\u0C7F]")
_LATIN = re.compile(r"[A-Za-z]")

# Sarvam / Pipecat language tags → session code
_SARVAM_TO_SESSION = {
    "en": LANG_EN,
    "en-in": LANG_EN,
    "en-us": LANG_EN,
    "hi": LANG_HI,
    "hi-in": LANG_HI,
    "ta": LANG_TA,
    "ta-in": LANG_TA,
    "te": LANG_TE,
    "te-in": LANG_TE,
}


def display_name(code: str) -> str:
    return DISPLAY_NAMES.get(normalize_session_lang(code) or code, code)


def normalize_session_lang(value: object | None) -> str | None:
    """Map arbitrary lang tags / Language enums to en-IN | hi-IN | ta-IN."""
    if value is None:
        return None

    if isinstance(value, Language):
        raw = str(value.value if hasattr(value, "value") else value)
    else:
        raw = str(value).strip()

    if not raw:
        return None

    key = raw.lower().replace("_", "-")
    if key in ("auto", "unknown", "none"):
        return None

    if key in _SARVAM_TO_SESSION:
        return _SARVAM_TO_SESSION[key]

    base = key.split("-")[0]
    return _SARVAM_TO_SESSION.get(base)


def to_cartesia_language(session_code: str) -> Language:
    code = normalize_session_lang(session_code) or LANG_EN
    if code == LANG_HI:
        return Language.HI
    if code == LANG_TA:
        return Language.TA
    if code == LANG_TE:
        return Language.TE
    return Language.EN


def significant_char_count(text: str) -> int:
    """Count letters / Indic chars (ignore punctuation & whitespace).

    The explicit range also captures Indic combining vowel marks (mātrās), which
    are not ``str.isalpha`` but are real language signal.
    """
    return sum(1 for ch in text if ch.isalpha() or "\u0900" <= ch <= "\u0C7F")


def detect_from_script(text: str) -> tuple[str | None, float]:
    """
    Heuristic script detection.

    Returns (session_code, confidence 0..1).
    Low confidence for short / mixed / empty text.
    """
    if not text or not text.strip():
        return None, 0.0

    dev = len(_DEVANAGARI.findall(text))
    tam = len(_TAMIL.findall(text))
    tel = len(_TELUGU.findall(text))
    lat = len(_LATIN.findall(text))
    total = dev + tam + tel + lat
    if total == 0:
        return None, 0.0

    # Prefer Indic scripts even when mixed with English (code-mixing). Pick the
    # dominant Indic script; English only wins when no Indic letters appear.
    indic = {LANG_TA: tam, LANG_HI: dev, LANG_TE: tel}
    top_lang = max(indic, key=lambda code: indic[code])
    top_count = indic[top_lang]
    if top_count >= 2:
        conf = min(1.0, top_count / max(total, 1) + 0.25)
        return top_lang, conf
    if lat >= 3 and top_count == 0:
        conf = min(1.0, lat / max(total, 1))
        return LANG_EN, conf

    # Weak signal
    if top_count > 0:
        return top_lang, 0.35
    if lat > 0:
        return LANG_EN, 0.35
    return None, 0.0


def detect_script_mode(text: str) -> str | None:
    """Roman/Latin vs native Indic letters. None if there is no letter signal."""
    if not text or not text.strip():
        return None
    if _DEVANAGARI.search(text) or _TAMIL.search(text) or _TELUGU.search(text):
        return SCRIPT_NATIVE
    if _LATIN.search(text):
        return SCRIPT_ROMAN
    return None


# Romanized Hindi / Tamil / Telugu tokens. Latin-only STT often tags these as
# English; they are the current Indic language written in Roman script. The
# patterns are prefix-based (\w*) so common suffixes / spelling variants are
# absorbed: enna+da, iruku/irukku, kasht(a)ma/kastama, samajh/samajhna, etc.
_ROMAN_HINDI = re.compile(
    r"\b("
    # Verbs / copulas
    r"hain?|nahin?|kar(?:na|o|ta|ti|te|tha|thi|thay)?|hota|hoti|hoga|hogi|hongi|"
    r"raha|rahi|rahe|rahega|karega|karegi|"
    r"samajh\w*|jaan\w*|bol\w*|bolna|bolne|"
    r"chahiye|chahta|chahti|"
    # Pronouns / demonstratives / possessives
    r"mujhe|mujhko|mujh|"
    r"aap|aapka|aapko|aapse|"
    r"tumhe|tumhara|tumko|tum|"
    r"hume|hamko|hamare|hamari|"
    r"kya|kyun|kyunki|kaise|kaisa|kaisi|"
    r"kuch|kuchh|kaun|kahan|kab|kitna|kitni|"
    r"ye|yeh|wo|woh|isko|usko|iska|uska|iski|uski|inko|unko|"
    # Adjectives / adverbs / discourse
    r"yaar|theek|achha|accha|haan|matlab|thoda|thodi|"
    r"bohot|bahut|abhi|lekin|magar|"
    r"mushkil\w*|kathin\w*|"
    r"aata|aati|aate|"
    r"malum|maloom|maalum|"
    # Common short markers rarely English
    r"hi\s+na|hain\s+na"
    r")\b",
    re.I,
)

_ROMAN_TAMIL = re.compile(
    r"\b("
    # Verbs / copulas / "is/was"
    r"iruk\w*|"
    r"panra\w*|panre\w*|panro\w*|panni\w*|pannu\w*|pannunga|"
    r"solli?\w*|sollu\w*|sonna\w*|sonnathu|"
    r"paaru\w*|paapom|paakiren|paakriya|"
    r"puriy\w*|"
    r"theriy\w*|"
    r"vendam|venum|venaam|"
    r"kudu\w*|kuduth\w*|"
    # Question / exclamation words (Tamil-specific, incl. "enna", "ennada")
    r"enn\w*(?:da|ppa|nga|di|do)?|"
    r"epdi|eppadi|eppo|yaaru|yenna|"
    r"ivlo|evlo|ivvalavu|evvalavu|"
    r"illai?|illey|"
    # Pronouns
    r"naan|nee|neenga|namma|avan|aval|avanga|adhu|idhu|ithu|andha|indha|"
    r"unga|ungal|ungalukku|"
    # Discourse / everyday
    r"seri|sari|appa|appo|inge|ange|dhaan|thaan|romba|konjam|"
    r"aana|aanaa|apparam|aprum|"
    # Struggle
    r"kasht?am\w*|kadinam\w*|"
    # Common Tamil enclitic-heavy words
    r"pona|pogura|poren|porom|varen|varom|"
    r"kekk\w*|paakalaam|paakalam"
    r")\b",
    re.I,
)

_ROMAN_TELUGU = re.compile(
    r"\b("
    # Verbs / copulas — anchored so they don't accidentally eat English
    # words like "understand" (un + \w+ was too greedy)
    r"unn\w+|undh?i\w*|leda|ledu|kadu|kadhu|kaadu|kaadhu|"
    r"matlad\w*|cheppa\w*|cheppu\w*|cheppandi|"
    r"telus\w*|telusuna|artham\w*|"
    r"chesa\w*|chestunna\w*|avutundhi|avutundi|"
    r"vasthund\w*|vasthav\w*|velthun\w*|potund\w*|"
    # Question / interrogatives
    r"enti|entra|enduku|enduku?ra|ela|elaa|eppudu|evaru|entha|"
    # Pronouns / demonstratives
    r"nenu|meeru|meru|nuvvu|nuv|manam|vaadu|aame|idi|adi|"
    # Discourse / struggle
    r"kashtam\w*|kashtamga|chala|chaala|konchem|konchem?ga|avunu"
    r")\b",
    re.I,
)

_ROMAN_INDIC = re.compile(
    _ROMAN_HINDI.pattern + "|" + _ROMAN_TAMIL.pattern + "|" + _ROMAN_TELUGU.pattern,
    re.I,
)

_EN_FUNCTION = re.compile(
    r"\b(the|this|that|these|those|because|explain|please|what|why|how|"
    r"could|would|should|about|with|from|have|does|don't|didn't|"
    r"really|understand|can|you|not|did)\b",
    re.I,
)


def looks_like_romanized_indic(text: str) -> bool:
    return bool(text and _ROMAN_INDIC.search(text))


_ROMAN_INDIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (LANG_HI, _ROMAN_HINDI),
    (LANG_TA, _ROMAN_TAMIL),
    (LANG_TE, _ROMAN_TELUGU),
)


def detect_romanized_indic_language(text: str) -> str | None:
    """Detect the specific Indic language in a Roman/Latin utterance.

    Returns the session code when the text contains a substantive amount of
    Roman-Indic tokens for one language (a clear switch signal); otherwise
    returns ``None`` for short/ambiguous input.
    """
    if not text:
        return None
    counts: dict[str, int] = {}
    for code, pattern in _ROMAN_INDIC_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            counts[code] = len({m.lower() for m in matches})
    if not counts:
        return None
    top_code, top_count = max(counts.items(), key=lambda item: item[1])
    others = [c for c, n in counts.items() if c != top_code and n >= top_count]
    if others:
        return None
    if top_count >= 2:
        return top_code
    return None


def looks_like_full_english(text: str) -> bool:
    """A sustained English clause — not a short ack or Romanized Indic."""
    if not text or not text.strip():
        return False
    script_lang, _ = detect_from_script(text)
    if script_lang in INDIC_LANGUAGES:
        return False
    if looks_like_romanized_indic(text):
        return False
    words = re.findall(r"[A-Za-z']+", text)
    return len(words) >= 5 and len(_EN_FUNCTION.findall(text)) >= 2


def resolve_detected_language(
    *,
    text: str,
    sarvam_language: object | None,
    min_chars: int = 8,
    min_confidence: float = 0.55,
) -> tuple[str | None, float, str]:
    """
    Combine Sarvam STT language with script heuristics.

    Returns (session_code | None, confidence, source).
    source is 'sarvam' | 'script' | 'none'.
    """
    chars = significant_char_count(text)
    if chars < min_chars:
        return None, 0.0, "none"

    script_code, script_conf = detect_from_script(text)
    sarvam_code = normalize_session_lang(sarvam_language)

    # Strong script evidence wins over a mismatched Sarvam tag (code-mix cases)
    if script_code in INDIC_LANGUAGES and script_conf >= min_confidence:
        if sarvam_code == script_code:
            return script_code, max(script_conf, 0.9), "sarvam+script"
        return script_code, script_conf, "script"

    if sarvam_code in SUPPORTED_LANGUAGES:
        # Soften Sarvam English on tiny Latin-only phrases already filtered by min_chars
        conf = 0.85 if script_code in (None, sarvam_code) else 0.6
        if conf >= min_confidence:
            return sarvam_code, conf, "sarvam"

    if script_code and script_conf >= min_confidence:
        return script_code, script_conf, "script"

    return None, 0.0, "none"


def is_supported(code: str | None) -> bool:
    return normalize_session_lang(code) in SUPPORTED_LANGUAGES


# A language name (any script) paired with a "speak/talk/answer/in ___" cue.
# The cue requirement stops a passing mention ("English is my second language")
# from flipping the conversation.
_LANG_NAME_TO_CODE: dict[str, str] = {
    "english": LANG_EN,
    "angrezi": LANG_EN,
    "angreji": LANG_EN,
    "इंग्लिश": LANG_EN,
    "अंग्रेज़ी": LANG_EN,
    "अंग्रेजी": LANG_EN,
    # A student speaking Tamil or Telugu asks for English in their own script.
    "இங்கிலீஷ்": LANG_EN,
    "ஆங்கில": LANG_EN,
    "ఇంగ్లీష్": LANG_EN,
    "ఆంగ్ల": LANG_EN,
    "hindi": LANG_HI,
    "हिंदी": LANG_HI,
    "हिन्दी": LANG_HI,
    "హిందీ": LANG_HI,
    "tamil": LANG_TA,
    "tamizh": LANG_TA,
    "தமிழ்": LANG_TA,
    "தமிழ": LANG_TA,
    "तमिल": LANG_TA,
    "తమిళ": LANG_TA,
    "telugu": LANG_TE,
    "తెలుగు": LANG_TE,
    "తెలుగులో": LANG_TE,
    "तेलुगु": LANG_TE,
}

# Verb / preposition cues that turn a language name into a request to switch.
# Also matches "do you know / can you speak / hindi aata hai kya" style
# capability questions: those imply the student wants to be answered in that
# language, so they count as an explicit switch.
_SWITCH_CUE = re.compile(
    r"(speak|talk|say|explain|reply|respond|answer|tell|switch|change|continue|"
    r"know|understand|"
    # Roman Hinglish capability questions
    r"malum|maloom|maalum|aata\s+hai|aati\s+hai|jaante|jante|bol\s+sakte|"
    r"bolte|samajhte|"
    # Roman Tanglish capability questions
    r"theriyuma|theriuma|puriyuma|pesa\s+mudiyuma|pesuveenga|pesalaam|"
    # Roman Tenglish capability questions
    r"telusa|telusuna|matladaga|artham|"
    r"बात|बोल|बता|समझा|कर|में|मे|"  # Hindi: talk/speak/tell/explain/do/in
    r"मालूम|जानते|आती|आता|"  # Hindi capability: know/comes to me
    r"பேச|சொல்|தெரிய|புரிய|முடியும|ல\b|லோ\b|"  # Tamil incl. know/understand/can
    r"మాట్లాడ|చెప్ప|తెలుస|అర్థ|లో\b|"  # Telugu incl. know/understand
    r"\bin\b|\bme\b|\bmein\b|\bla\b|\blo\b)",
    re.I,
)


def detect_language_request(text: str) -> str | None:
    """Explicit "switch to <language>" request → session code, else None.

    Deliberate user preference. It overrides automatic detection, so it must not
    fire on a mere mention of a language name.
    """
    if not text:
        return None
    lowered = text.lower()
    for name, code in _LANG_NAME_TO_CODE.items():
        idx = lowered.find(name.lower()) if name.isascii() else text.find(name)
        if idx < 0:
            continue
        # Require a switch cue somewhere in the utterance, not just the name.
        window = text[max(0, idx - 24): idx + len(name) + 24]
        if _SWITCH_CUE.search(window):
            return code
    return None
