"""Isolated safety layer — intent detection, pause, and canned replies.

No LLM is involved. Ordinary tutoring must remain a no-op.
"""

from __future__ import annotations

from pathlib import Path

from languages import LANG_EN, LANG_HI, LANG_TA, LANG_TE
from protocol import SERVER_SAFETY_ALERT
from tutor.safety import (
    SafetyKind,
    SafetyPhase,
    SafetyStore,
    classify,
    spoken_for,
    spoken_immediate_danger,
    spoken_self_harm,
)


def _cat(text: str) -> str | None:
    hit = classify(text)
    return hit.category if hit else None


def test_english_suicide_and_self_harm_statements():
    phrases = [
        "I feel like committing suicide",
        "It's boring, I just feel like committing suicide.",
        "I want to kill myself",
        "I don't want to live",
        "How can I die?",
        "I want to hurt myself",
        "I can't go on anymore",
        "I want to die",
        "I've been thinking about killing myself",
        "How do I end my life?",
        "I wish I were dead",
        "I don't wanna live anymore",
        "life is not worth living",
    ]
    for phrase in phrases:
        assert _cat(phrase) == "self_harm", phrase


def test_english_harm_to_others_statements():
    phrases = [
        "How to murder someone?",
        "I want to hurt someone",
        "I want to kill him",
        "How can I kill somebody?",
        "I'm going to hurt her",
        "How do I murder someone",
    ]
    for phrase in phrases:
        assert _cat(phrase) == "harm_to_others", phrase


def test_hindi_and_hinglish_equivalents():
    phrases = [
        "मुझे मरना है",
        "मैं आत्महत्या करना चाहता हूँ",
        "जीना नहीं चाहता",
        "खुद को मार दूंगा",
        "कैसे मरूँ",
        "mujhe marna hai",
        "main suicide karna chahta hoon",
        "jeena nahi chahta",
        "khud ko maar dunga",
        "kaise marun",
        "main jeena nahi chahta",
        "kisi ko kaise maare",
        "किसी को मारना है",
        "mujhe kisi ko nuksan pahunchana hai",
    ]
    expected = {
        "kisi ko kaise maare": "harm_to_others",
        "किसी को मारना है": "harm_to_others",
        "mujhe kisi ko nuksan pahunchana hai": "harm_to_others",
    }
    for phrase in phrases:
        got = _cat(phrase)
        want = expected.get(phrase, "self_harm")
        assert got == want, f"{phrase!r} -> {got} (want {want})"


def test_tamil_and_tanglish_equivalents():
    phrases = [
        "நான் சாக விரும்புகிறேன்",
        "தற்கொலை செய்ய நினைக்கிறேன்",
        "எப்படி சாகலாம்",
        "வாழ விரும்பல",
        "naan saaga virumburen",
        "tharkolai seiyanum",
        "vazha virumbala",
        "eppadi saagalam",
        "ennai kollanum",
        "oruthanai kollanum",
        "ஒருவனை கொல்லணும்",
        "yaaraiyaavadhu kayapaduthanum",
    ]
    expected = {
        "oruthanai kollanum": "harm_to_others",
        "ஒருவனை கொல்லணும்": "harm_to_others",
        "yaaraiyaavadhu kayapaduthanum": "harm_to_others",
    }
    for phrase in phrases:
        got = _cat(phrase)
        want = expected.get(phrase, "self_harm")
        assert got == want, f"{phrase!r} -> {got} (want {want})"


def test_telugu_and_tenglish_equivalents():
    phrases = [
        "నేను చావాలనుకుంటున్నాను",
        "ఆత్మహత్య చేసుకోవాలి",
        "ఎలా చావాలి",
        "బతకాలని లేదు",
        "nenu chaavali anukuntunna",
        "aatmahatya cheskovali",
        "bathakali anipiyyatledu",
        "ela chavali",
        "nannu champukovali",
        "evvarini champali",
        "ఎవరినైనా చంపాలి",
        "evarnaina himsinchali",
    ]
    expected = {
        "evvarini champali": "harm_to_others",
        "ఎవరినైనా చంపాలి": "harm_to_others",
        "evarnaina himsinchali": "harm_to_others",
    }
    for phrase in phrases:
        got = _cat(phrase)
        want = expected.get(phrase, "self_harm")
        assert got == want, f"{phrase!r} -> {got} (want {want})"


def test_benign_die_and_kill_phrases_do_not_trigger():
    phrases = [
        "my phone died",
        "the battery died",
        "I don't want to live there",
        "I don't want to live in Delhi",
        "I can't go on to the next chapter",
        "this problem is killing me",
        "I'm dying to know the answer",
        "this is a do or die chapter",
        "let's kill time until the exam",
        "what is suicide",
        "who murdered the king",
        "the terms will die out",
        "Can you explain substitution?",
        "how did the dinosaur die",
        "hurt my chances of passing",
    ]
    for phrase in phrases:
        assert classify(phrase) is None, phrase


def test_normal_tutoring_is_not_intercepted():
    store = SafetyStore()
    result = store.apply(
        "Can you explain the substitution method?",
        language=LANG_EN,
        now=1_000.0,
    )
    assert result is None
    assert store.paused is False
    assert store.phase is SafetyPhase.IDLE


def test_alert_pauses_tutoring_and_emits_internal_event():
    store = SafetyStore()
    result = store.apply("I want to kill myself", language=LANG_EN, now=1_700.5)
    assert result is not None
    assert result.swallow is True
    assert result.drop_last_user is True
    assert result.kind is SafetyKind.ALERT
    assert store.paused is True
    assert result.event is not None
    assert result.event["type"] == SERVER_SAFETY_ALERT == "safety_alert"
    assert result.event["category"] == "self_harm"
    assert result.event["severity"] == "high"
    assert result.event["timestamp"] == 1_700_500
    assert "glad you told me" in result.spoken.lower()
    assert "immediate danger" in result.spoken.lower()


def test_harm_to_others_uses_the_harm_script():
    store = SafetyStore()
    result = store.apply("How to murder someone?", language=LANG_EN, now=2.0)
    assert result is not None
    assert result.event["category"] == "harm_to_others"
    assert "can't help with hurting someone" in result.spoken.lower()
    assert "how to" not in result.spoken.lower()


def test_math_turn_resumes_tutoring_after_a_pause():
    store = SafetyStore()
    store.apply("I don't want to live", language=LANG_EN, now=1.0)
    result = store.apply(
        "Okay, explain substitution",
        language=LANG_EN,
        now=2.0,
    )
    assert result is not None
    assert result.kind is SafetyKind.RESUME
    assert result.swallow is False
    assert result.drop_last_user is False
    assert store.paused is False


def test_two_unrelated_math_turns_escape_holding():
    """A crisis keyword must not swallow the rest of the lesson.

    Detection is unchanged: the first line still trips classify(). The next
    two turns do not match resume or danger phrases, so tutoring resumes on
    the second.
    """
    from io import StringIO

    from loguru import logger

    from tutor.safety import utterance_hash

    buf = StringIO()
    sink_id = logger.add(buf, format="{message}")
    try:
        store = SafetyStore()
        trigger = "How can I die?"
        alert = store.apply(trigger, language=LANG_EN, now=1.0)
        assert alert is not None
        assert alert.kind is SafetyKind.ALERT
        assert store.paused is True
        logs = buf.getvalue()
        assert "safety_turn_swallowed" in logs
        assert utterance_hash(trigger) in logs
        assert trigger not in logs
        assert "self_harm" in logs

        first = "What is the value of x here?"
        holding = store.apply(first, language=LANG_EN, now=2.0)
        assert holding is not None
        assert holding.kind is SafetyKind.HOLDING
        assert holding.swallow is True
        assert store.paused is True
        assert utterance_hash(first) in buf.getvalue()
        assert first not in buf.getvalue()

        second = "I got 12 as the answer"
        resumed = store.apply(second, language=LANG_EN, now=3.0)
        assert resumed is not None
        assert resumed.kind is SafetyKind.RESUME
        assert resumed.swallow is False
        assert store.paused is False
        assert store.last_category == "self_harm"
        assert second not in buf.getvalue()
    finally:
        logger.remove(sink_id)


def test_immediate_danger_offers_tele_manas():
    store = SafetyStore()
    store.apply("I feel like committing suicide", language=LANG_EN, now=1.0)
    result = store.apply("Yes, right now", language=LANG_EN, now=2.0)
    assert result is not None
    assert result.kind is SafetyKind.IMMEDIATE_DANGER
    assert result.swallow is True
    spoken = result.spoken.lower()
    assert "tele-manas" in spoken
    assert "1 4 4 1 6" in spoken or "14416" in spoken
    assert "jump" not in spoken
    assert "pills" not in spoken


def test_safety_replies_follow_active_language():
    hi = spoken_self_harm(LANG_HI)
    ta = spoken_self_harm(LANG_TA)
    te = spoken_self_harm(LANG_TE)
    assert any("\u0900" <= ch <= "\u097F" for ch in hi)
    assert any("\u0B80" <= ch <= "\u0BFF" for ch in ta)
    assert any("\u0C00" <= ch <= "\u0C7F" for ch in te)
    assert spoken_for("harm_to_others", LANG_HI) != spoken_for("self_harm", LANG_HI)
    assert "14416" in spoken_immediate_danger(LANG_HI) or "1 4 4 1 6" in spoken_immediate_danger(
        LANG_HI
    )


def test_scripts_are_not_moralizing_and_give_no_methods():
    forbidden = (
        "a wise person",
        "you should be ashamed",
        "jump off",
        "use a knife",
        "here's how",
        "hang yourself",
    )
    for language in (LANG_EN, LANG_HI, LANG_TA, LANG_TE):
        for category in ("self_harm", "harm_to_others"):
            text = spoken_for(category, language).lower()
            for phrase in forbidden:
                assert phrase not in text, (language, category, phrase)
        assert "wise person" not in spoken_immediate_danger(language).lower()


def test_crisis_user_turn_is_dropped_from_llm_context():
    from pipecat.processors.aggregators.llm_context import LLMContext
    from processors.safety import drop_last_user_message

    ctx = LLMContext(
        messages=[
            {"role": "system", "content": "tutor"},
            {"role": "user", "content": "I want to kill myself"},
        ]
    )
    assert drop_last_user_message(ctx) is True
    assert all(m.get("role") != "user" for m in ctx.get_messages())


def test_processor_swallows_crisis_and_lets_math_resume():
    import asyncio

    from pipecat.frames.frames import (
        LLMContextFrame,
        OutputTransportMessageFrame,
        TTSSpeakFrame,
    )
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.frame_processor import FrameDirection
    from processors.safety import SafetyProcessor
    from processors.session_context import SessionContextStore
    from tutor.safety import SafetyStore

    async def run() -> None:
        ctx = LLMContext(
            messages=[
                {"role": "system", "content": "tutor"},
                {"role": "user", "content": "I want to kill myself"},
            ]
        )
        proc = SafetyProcessor(
            store=SafetyStore(),
            llm_context=ctx,
            session_store=SessionContextStore(),
            get_language=lambda: LANG_EN,
        )
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        proc.push_frame = capture  # type: ignore[method-assign]

        await proc.process_frame(
            LLMContextFrame(context=ctx),
            FrameDirection.DOWNSTREAM,
        )
        assert not any(isinstance(f, LLMContextFrame) for f in pushed)
        alert = next(f for f in pushed if isinstance(f, OutputTransportMessageFrame))
        assert alert.message["type"] == "safety_alert"
        assert alert.message["category"] == "self_harm"
        assert alert.message["severity"] == "high"
        spoken = next(f for f in pushed if isinstance(f, TTSSpeakFrame))
        assert "glad you told me" in spoken.text.lower()
        assert "immediate danger" in spoken.text.lower()
        assert spoken.append_to_context is False
        assert proc._store.paused

        pushed.clear()
        crisis = "It's boring, I just feel like committing suicide."
        ctx.messages.append({"role": "user", "content": crisis})
        from pipecat.frames.frames import LLMMessagesAppendFrame

        await proc.process_frame(
            LLMMessagesAppendFrame(
                messages=[{"role": "user", "content": crisis}],
                run_llm=True,
            ),
            FrameDirection.DOWNSTREAM,
        )
        assert not any(isinstance(f, LLMMessagesAppendFrame) for f in pushed)
        assert any(
            isinstance(f, OutputTransportMessageFrame)
            and f.message.get("type") == "safety_alert"
            for f in pushed
        )

        pushed.clear()
        ctx.messages.append({"role": "user", "content": "explain substitution"})
        await proc.process_frame(
            LLMContextFrame(context=ctx),
            FrameDirection.DOWNSTREAM,
        )
        assert any(isinstance(f, LLMContextFrame) for f in pushed)
        assert proc._store.paused is False

    asyncio.run(run())


def test_voice_pipeline_keeps_safety_off_the_audio_path():
    source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assembled = source.split("pipeline = Pipeline", 1)[1]
    for name in (
        "stt",
        "user_aggregator",
        "text_input",
        "safety",
        "study_break",
        "tutor_turn",
        "llm",
        "tts",
    ):
        assert name in assembled, name
    assert assembled.index("stt") < assembled.index("safety")
    assert assembled.index("user_aggregator") < assembled.index("safety")
    assert assembled.index("text_input") < assembled.index("safety")
    assert assembled.index("safety") < assembled.index("study_break")
    assert assembled.index("safety") < assembled.index("tutor_turn")
    assert assembled.index("safety") < assembled.index("\n            llm,")
