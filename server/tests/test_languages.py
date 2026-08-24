"""Unit tests for multilingual language detection / mapping."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from languages import (  # noqa: E402
    LANG_EN,
    LANG_HI,
    LANG_TA,
    LANG_TE,
    SCRIPT_NATIVE,
    SCRIPT_ROMAN,
    SUPPORTED_LANGUAGES,
    detect_from_script,
    detect_language_request,
    detect_romanized_indic_language,
    detect_script_mode,
    display_name,
    looks_like_full_english,
    looks_like_romanized_indic,
    normalize_session_lang,
    resolve_detected_language,
    significant_char_count,
    to_cartesia_language,
)
from pipecat.transcriptions.language import Language  # noqa: E402


def test_supported_languages_config():
    assert list(SUPPORTED_LANGUAGES) == [LANG_EN, LANG_HI, LANG_TA, LANG_TE]


def test_normalize_session_lang():
    assert normalize_session_lang("en") == LANG_EN
    assert normalize_session_lang("en-IN") == LANG_EN
    assert normalize_session_lang("hi-IN") == LANG_HI
    assert normalize_session_lang("ta-IN") == LANG_TA
    assert normalize_session_lang("te-IN") == LANG_TE
    assert normalize_session_lang("te") == LANG_TE
    assert normalize_session_lang("auto") is None
    assert normalize_session_lang(Language.HI_IN) == LANG_HI
    assert normalize_session_lang(Language.TA_IN) == LANG_TA
    assert normalize_session_lang(Language.TE_IN) == LANG_TE


def test_display_names():
    assert display_name(LANG_EN) == "English"
    assert display_name(LANG_HI) == "Hindi"
    assert display_name(LANG_TA) == "Tamil"
    assert display_name(LANG_TE) == "Telugu"


def test_cartesia_mapping():
    assert to_cartesia_language(LANG_EN) == Language.EN
    assert to_cartesia_language(LANG_HI) == Language.HI
    assert to_cartesia_language(LANG_TA) == Language.TA
    assert to_cartesia_language(LANG_TE) == Language.TE


def test_telugu_script():
    code, conf = detect_from_script("ఈ equation ను ఎలా solve చేయాలి")
    assert code == LANG_TE
    assert conf >= 0.5


def test_telugu_conversation_resolve():
    detected, conf, source = resolve_detected_language(
        text="ఈ slide ఏమి చెబుతుంది సార్",
        sarvam_language="te-IN",
    )
    assert detected == LANG_TE


def test_hindi_with_one_english_word_stays_hindi():
    # "How do we solve this equation?" in Hindi — one English maths word.
    code, conf = detect_from_script("इस equation को कैसे solve करें")
    assert code == LANG_HI


def test_significant_char_count_counts_telugu():
    assert significant_char_count("తెలుగు") >= 5


# ── Explicit language-switch requests override auto-detection ──────────────


def test_explicit_switch_to_english_from_hindi_speech():
    assert detect_language_request("अब English में समझाओ") == LANG_EN


def test_explicit_switch_to_hindi():
    assert detect_language_request("अब हिंदी में बताओ") == LANG_HI
    assert detect_language_request("talk to me in Hindi") == LANG_HI


def test_explicit_switch_to_tamil():
    assert detect_language_request("தமிழ்ல பேசுங்க") == LANG_TA
    assert detect_language_request("speak in Tamil please") == LANG_TA


def test_explicit_switch_to_telugu():
    assert detect_language_request("తెలుగులో మాట్లాడండి") == LANG_TE
    assert detect_language_request("explain in Telugu") == LANG_TE


def test_switch_request_written_in_the_student_own_script():
    """A Tamil speaker asks for English in Tamil script, not Latin."""
    assert (
        detect_language_request(
            "சரி இதெல்லாம் வேணாம் நீ இங்கிலீஷ்லேயே பேசி என்கிட்ட டாக்கிங் இங்கிலீஷ்"
        )
        == LANG_EN
    )
    assert detect_language_request("இதை ஆங்கிலத்தில் சொல்லுங்க") == LANG_EN
    assert detect_language_request("ఇంగ్లీష్‌లో చెప్పండి") == LANG_EN
    assert detect_language_request("तमिल में समझाओ") == LANG_TA


def test_capability_question_counts_as_switch_hindi_roman():
    for phrase in (
        "hindi malum hai kya",
        "hindi aata hai kya",
        "hindi bol sakte ho",
        "kya aap hindi jaante ho",
        "do you know hindi",
        "can you speak hindi",
    ):
        assert detect_language_request(phrase) == LANG_HI, phrase


def test_capability_question_counts_as_switch_tamil_roman():
    for phrase in (
        "tamil theriyuma",
        "tamil pesa mudiyuma",
        "do you know tamil",
        "can you speak tamil",
    ):
        assert detect_language_request(phrase) == LANG_TA, phrase


def test_capability_question_counts_as_switch_telugu_roman():
    for phrase in (
        "telugu telusa",
        "telugu matladagaligaru",
        "do you know telugu",
    ):
        assert detect_language_request(phrase) == LANG_TE, phrase


def test_capability_question_counts_as_switch_native_script():
    assert detect_language_request("तमिल मालूम है क्या") == LANG_TA
    assert detect_language_request("தமிழ் தெரியுமா") == LANG_TA
    assert detect_language_request("తెలుగు తెలుసా") == LANG_TE
    assert detect_language_request("हिंदी आती है क्या") == LANG_HI


def test_mere_mention_is_not_a_switch_request():
    assert detect_language_request("English is my favourite subject") is None
    assert detect_language_request("I like the Tamil movie") is None
    # "இந்திய" (Indian) contains no language request.
    assert detect_language_request("இந்திய கணிதம் பற்றி சொல்லுங்க") is None


def test_english_script():
    code, conf = detect_from_script("Hello, I need help with my account balance")
    assert code == LANG_EN
    assert conf >= 0.5


def test_hindi_script():
    code, conf = detect_from_script("मेरा अकाउंट ब्लॉक हो गया है")
    assert code == LANG_HI
    assert conf >= 0.5


def test_tamil_script():
    code, conf = detect_from_script("என்னோட account block ஆயிடுச்சு")
    assert code == LANG_TA
    assert conf >= 0.5


def test_short_utterance_ignored():
    detected, conf, source = resolve_detected_language(
        text="Hi",
        sarvam_language="en-IN",
        min_chars=8,
    )
    assert detected is None
    assert source == "none"
    assert significant_char_count("Hi") < 8


def test_english_conversation_resolve():
    detected, conf, source = resolve_detected_language(
        text="I lost my debit card yesterday",
        sarvam_language="en-IN",
    )
    assert detected == LANG_EN
    assert conf >= 0.55


def test_hindi_conversation_resolve():
    detected, conf, source = resolve_detected_language(
        text="मुझे balance check करना है प्लीज",
        sarvam_language="hi-IN",
    )
    assert detected == LANG_HI


def test_tamil_conversation_resolve():
    detected, conf, source = resolve_detected_language(
        text="சரி account balance சொல்லுங்க",
        sarvam_language="ta-IN",
    )
    assert detected == LANG_TA


def test_english_to_hindi_switch_signal():
    d1, _, _ = resolve_detected_language(
        text="I need help with my loan payment today",
        sarvam_language="en-IN",
    )
    d2, _, _ = resolve_detected_language(
        text="मेरा अकाउंट ब्लॉक हो गया है अभी",
        sarvam_language="hi-IN",
    )
    assert d1 == LANG_EN
    assert d2 == LANG_HI
    assert d1 != d2


def test_hindi_to_tamil_switch_signal():
    d1, _, _ = resolve_detected_language(
        text="मुझे OTP नहीं मिला है अभी तक",
        sarvam_language="hi-IN",
    )
    d2, _, _ = resolve_detected_language(
        text="என்னோட account block ஆயிடுச்சு சார்",
        sarvam_language="ta-IN",
    )
    assert d1 == LANG_HI
    assert d2 == LANG_TA


def test_tamil_to_english_switch_signal():
    d1, _, _ = resolve_detected_language(
        text="கொஞ்சம் wait பண்ணுங்க please",
        sarvam_language="ta-IN",
    )
    d2, _, _ = resolve_detected_language(
        text="Okay please tell me my account balance",
        sarvam_language="en-IN",
    )
    assert d1 == LANG_TA
    assert d2 == LANG_EN


def test_mixed_hindi_english_prefers_hindi_script():
    detected, conf, source = resolve_detected_language(
        text="मेरा account block हो गया है",
        sarvam_language="en-IN",  # mismatched on purpose
    )
    assert detected == LANG_HI
    assert source in ("script", "sarvam+script")


def test_low_confidence_keeps_none_for_ambiguous():
    detected, conf, source = resolve_detected_language(
        text="...",
        sarvam_language=None,
        min_chars=1,
        min_confidence=0.9,
    )
    assert detected is None


def test_script_mode_roman_vs_native():
    assert detect_script_mode("enna panrom") == SCRIPT_ROMAN
    assert detect_script_mode("இந்த equation") == SCRIPT_NATIVE
    assert detect_script_mode("इस slide को") == SCRIPT_NATIVE
    assert detect_script_mode("...") is None


def test_romanized_indic_is_not_full_english():
    assert looks_like_romanized_indic("enna solve pannu")
    assert looks_like_romanized_indic("theek hai next")
    assert not looks_like_full_english("enna solve pannu")
    assert not looks_like_full_english("ok next slide")
    assert looks_like_full_english("can you explain this equation")
    assert looks_like_full_english("I really did not understand that part")


def test_detect_romanized_indic_language_picks_specific_language():
    assert detect_romanized_indic_language("yaar mujhe samajh nahi aa raha") == LANG_HI
    assert detect_romanized_indic_language("enna pannu neenga sollunga") == LANG_TA
    assert detect_romanized_indic_language("nenu enti cheppu unnadu") == LANG_TE


def test_roman_tamil_handles_common_variants_and_enclitics():
    # "ennada" (enna+da), "ivlo", "kastama" (no h), "iruku" (single k)
    assert detect_romanized_indic_language("ennada ivlo kastama iruku") == LANG_TA
    assert detect_romanized_indic_language("puriyala saar romba kastam") == LANG_TA
    assert detect_romanized_indic_language("konjam thaan pannunga") == LANG_TA


def test_roman_hindi_handles_common_variants():
    assert detect_romanized_indic_language("yeh concept bahut mushkil hai") == LANG_HI
    assert detect_romanized_indic_language("mujhe samajhna nahi aa raha yaar") == LANG_HI


def test_roman_telugu_handles_common_variants():
    assert detect_romanized_indic_language("naaku artham kavatledu chala kashtam") == LANG_TE


def test_detect_romanized_indic_language_none_for_short_or_english():
    assert detect_romanized_indic_language("okay next slide please") is None
    assert detect_romanized_indic_language("hai") is None  # single token, ambiguous
    assert detect_romanized_indic_language("") is None


def test_context_across_languages_is_caller_responsibility():
    """Memory is language-independent: same session keeps turns; we only map langs."""
    turns = [
        ("I lost my debit card.", "en-IN", LANG_EN),
        ("उसका replacement चाहिए", "hi-IN", LANG_HI),
    ]
    codes = []
    for text, sarvam, expected in turns:
        detected, _, _ = resolve_detected_language(text=text, sarvam_language=sarvam)
        codes.append(detected)
        assert detected == expected
    assert codes == [LANG_EN, LANG_HI]
