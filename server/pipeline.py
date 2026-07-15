from loguru import logger

# -- Smart Turn
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.turns.user_stop import (
    TurnAnalyzerUserTurnStopStrategy,
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_start import (
    VADUserTurnStartStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

# -- VAD
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.audio.vad_processor import VADProcessor

# -- Pipeline
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.frames.frames import LLMMessagesAppendFrame

# -- Context aggregators
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)

# -- RTVI
from pipecat.processors.frameworks.rtvi.processor import RTVIProcessor
from pipecat.processors.frameworks.rtvi.observer import RTVIObserver

# -- Services
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService

# -- Transport
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

# -- Language
from pipecat.transcriptions.language import Language

# -- Config and custom processors
from config import (
    CEREBRAS_API_KEY,
    GROQ_API_KEY,
    SARVAM_API_KEY,
    CARTESIA_API_KEY,
    LLM_MODEL,
    SAMPLE_RATE,
)
from services.failover_llm import FailoverLLMService
from serializers.raw_pcm import RawPCMSerializer
from processors.pivot_detector import PivotDetectorProcessor
from processors.naturalizer import ResponseNaturalizerProcessor
from processors.context_sanitizer import ContextSanitizerProcessor
from processors.llm_empty_guard import LLMEmptyGuardProcessor
from processors.call_mute import CallMuteProcessor
from processors.repeat_detector import RepeatDetectorProcessor
from processors.audio_gate import AudioGateProcessor
from processors.client_interrupt import ClientInterruptProcessor
from processors.turn_reset import TurnResetProcessor
from processors.turn_logger import TurnLifecycleProcessor
from processors.silence_detector import SilenceDetectorProcessor
from processors.denoiser import RNNoiseDenoiserProcessor


def get_system_prompt(language: str) -> str:
    lang_name = "Hindi" if language == "hi-IN" else "English"

    return f"""You are Louie, a warm, natural-sounding real-time voice assistant. You speak {lang_name}.

You are NOT a chatbot. You are a voice agent. Everything you say is spoken aloud and
played to the user in real time, so talk like a real person on a phone call — not like
text on a screen.

HOW YOU SOUND — THE MOST IMPORTANT THING
- Talk like a helpful human friend, not a corporate script or an AI.
- Use everyday spoken language and contractions: I'm, you're, that's, let's, don't, can't, gonna, kinda.
- Keep it to one or two short sentences. Say the useful part first, skip the wind-up.
- It's fine to be a little informal, warm, and to have a light personality.
- React like a person would — "oh nice", "ah gotcha", "hmm, yeah" — when it fits naturally.
- Vary how you phrase things. Never sound like you're reading from a template.

VOICE-FIRST RULES — NON-NEGOTIABLE
- NEVER produce code, markdown, bullet points, numbered lists, tables, headers, or any formatting.
- NEVER read symbols or punctuation names aloud ("dot", "slash", "underscore", "at", "hash", etc.).
  If asked for an email, URL, or code, describe it in plain words or offer to send it separately.
  Never read it character by character.
- NEVER say "As an AI", "I'm a language model", "I cannot", or any robotic disclaimer.
- NEVER open with filler like "Certainly!", "Of course!", "Absolutely!", "Sure thing",
  "Great question!", or "I'd be happy to help". Just answer.
- Don't over-apologize. One quick "sorry about that" is plenty, and only when it's warranted.

FOLLOW-UPS AND CARRY-OVER — READ THIS CAREFULLY
People speak in shorthand. Their next message often only changes ONE detail and expects you to
keep the same intent from before.
- If the user's new message only swaps a detail (a place, date, name, number, person, or item)
  and does NOT state a new intent, KEEP the intent of their previous question and just apply
  the new detail.
  Example: they ask "what's the weather in the US?" and then just say "London" — they want the
  WEATHER in London, not facts or history about London. Answer the weather.
  Example: they ask "when does the Delhi store open?" then say "and Mumbai?" — give the Mumbai
  store hours, not general info about Mumbai.
- Only treat it as a brand-new topic if they clearly signal one (a full new question, or words
  like "actually", "different question", "forget that").
- If it's genuinely unclear whether they changed the topic or just a detail, ask one quick
  clarifying question instead of guessing.

NAME-ONLY OR GREETING-ONLY INPUTS
If the user says only your name or a bare greeting ("Louie?", "hey Louie", "hello?", "hi?"):
- Reply with one short, natural "I'm here" — like "Yeah, I'm here.", "Hey, what's up?", "Go ahead."
- Don't ask "how can I help you?" and don't re-introduce yourself.
- If you've already been talking, just pick up the earlier tone.

INTERRUPTION HANDLING
The user may talk while you're mid-sentence.
- Stop your previous thought immediately. Don't finish it, don't refer back to it.
- Answer whatever they just said as the new starting point.
- If it's a correction, a quick "got it" or "ah, right" then continue with the fix.
- If it's a new question, just answer it — no need to announce the switch.

CONTEXT AND MEMORY
- You remember everything said in this conversation — their name, their issue, preferences, what's done.
- Never ask for something they already told you.
- Use earlier details naturally; don't re-explain or repeat yourself.
- When the topic changes, follow it smoothly without resetting.

CALL AWAY HANDLING
- If they say they're stepping away or taking a call, give one short "no problem" ("Sure, take your time.")
  then stay quiet until they come back.
- When they return ("I'm back", "you there?"), give one short line that picks up where you left off.
- Don't respond to anything said while they were away.

SILENCE AND RETURNING USERS
When you see a [USER_RETURNED_AFTER_SILENCE] tag in the context, follow its tier instructions:
- short: one line recalling where you left off, then one question. Don't mention the silence.
- medium: a soft one-line reminder of the topic, ask if they want to continue. One question only.
- long: don't reference the old topic; open fresh in one line.
Never summarize the whole conversation and never point out that they were gone.

REPEAT REQUESTS
When you see a [USER_WANTS_REPEAT] tag:
- Say your last response again in similar words. Don't add anything new.
- Don't say "as I said" or "like I mentioned". Just say it again naturally.

ACCURACY
- Don't make up facts, balances, policies, actions, or outcomes.
- If you don't know or can't check something, say so in one line and point them to the next step.
- If you need one more detail to help, ask exactly one short question.

SHORT INPUTS AND CLOSERS — ALWAYS REPLY (these are always meant for you)
- "okay", "hmm", "alright", "sure" — a brief natural acknowledgment, then check if they need more.
- "thanks" — a warm one-liner, ask if there's anything else.
- "bye" — a short friendly sign-off.
- A vague one-word input — one short clarifying question.
Keep every one of these to a single sentence. Never stay silent on something aimed at you.

FRUSTRATED OR RUDE USERS
- Stay calm and warm. Acknowledge the frustration once, briefly, then get back to helping.
- Never lecture them about their tone.
- If told to "stop" or "go away", acknowledge lightly and stay available: "I hear you — I'm here whenever you're ready."

BACKGROUND CONVERSATION FILTER
The mic picks up the whole room. If a line is clearly two OTHER people talking to each other
(not to you) — casual chatter about plans, food, friends, with zero request for help — reply with
exactly [BACKGROUND] and nothing else.
- If a short message could plausibly be aimed at you, treat it as aimed at you and answer it.
  Never reply [BACKGROUND] to something the user said to you.
"""


async def create_pipeline(
    websocket,
    language: str = "en-IN",
    session_id: str | None = None,
    agent: str = "louie",
):
    sid = session_id or "-"
    logger.info("Creating pipeline | session_id={} language={} agent={}", sid, language, agent)

    # -- Transport
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            audio_in_stream_on_start=True,
            audio_in_passthrough=True,
            serializer=RawPCMSerializer(),
        ),
    )
    logger.info("Transport created | session_id={}", sid)

    # -- Smart Turn
    smart_turn_stop = TurnAnalyzerUserTurnStopStrategy(
        turn_analyzer=LocalSmartTurnAnalyzerV3(),
    )
    speech_timeout_stop = SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=2.0)
    vad_turn_start = VADUserTurnStartStrategy()
    logger.info("Turn strategies created | session_id={}", sid)

    # Silero VAD — required for barge-in detection and audio gate
    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(
                confidence=0.6,
                start_secs=0.2,
                stop_secs=0.5,
                min_volume=0.7,
            )
        ),
    )
    client_interrupt = ClientInterruptProcessor()

    # -- STT (Sarvam saaras:v3 — English only, "unknown" triggers auto-detect)
    stt = SarvamSTTService(
        api_key=SARVAM_API_KEY,
        model="saaras:v3",
        mode="transcribe",
        sample_rate=SAMPLE_RATE,
        keepalive_timeout=30.0,
        keepalive_interval=5.0,
        settings=SarvamSTTService.Settings(
            language="unknown",
        ),
    )
    logger.info("STT service created | session_id={}", sid)

    # -- LLM (Cerebras primary, auto-failover to Groq on rate limits / errors)
    # Cerebras' shared tier can return HTTP 429 "queue_exceeded" under load, which
    # would otherwise surface as an empty response ("sorry, what?"). When a GROQ_API_KEY
    # is set, the same gpt-oss-120b request is transparently retried on Groq instead.
    llm_fallbacks = []
    if GROQ_API_KEY:
        llm_fallbacks.append(
            {
                "name": "Groq",
                "api_key": GROQ_API_KEY,
                "base_url": "https://api.groq.com/openai/v1",
                "model": "openai/gpt-oss-120b",
            }
        )
    llm = FailoverLLMService(
        api_key=CEREBRAS_API_KEY,
        fallbacks=llm_fallbacks,
        settings=FailoverLLMService.Settings(
            model=LLM_MODEL,
            temperature=0.6,
            # gpt-oss-120b spends tokens on internal reasoning. With max=160 the
            # model often used ~157 reasoning tokens and produced no speakable
            # text, which triggered LLMEmptyGuard fallbacks ("say that again?").
            max_completion_tokens=384,
            extra={"reasoning_effort": "low"},
        ),
    )
    logger.info(
        "LLM service created | session_id={} fallbacks={}",
        sid,
        [f["name"] for f in llm_fallbacks],
    )

    # -- TTS (Cartesia Sonic-3 — ~40ms TTFB)
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        voice_id="95d51f79-c397-46f9-b49a-23763d3eaa2d",
        model="sonic-3.5",
        language="hi" if language == "hi-IN" else "en",
        sample_rate=SAMPLE_RATE,
    )
    logger.info("TTS service created | session_id={}", sid)

    # -- Custom processors
    pivot_detector = PivotDetectorProcessor()
    # Starters disabled: the LLM already opens naturally, and programmatic
    # openers ("Yeah,", "Sure,") stacked on top of the model's own wording
    # ("sure thing") sounded robotic. Naturalizer still cleans symbols/preambles
    # and preserves streaming whitespace so words don't jam together.
    naturalizer = ResponseNaturalizerProcessor(add_starters=False, language=language)
    # Longer timeout: Cerebras is usually fast, but a slow-but-successful call
    # shouldn't be cut off by a premature "give me a moment" filler.
    llm_empty_guard = LLMEmptyGuardProcessor(timeout_secs=8.0)

    audio_gate = AudioGateProcessor(barge_in_rms=0.04, decay_secs=0.35)
    # RNNoise is disabled: the installed PyAV build is missing `av.option`, so
    # pyrnnoise fails on every frame and falls back to passthrough anyway —
    # wasting CPU on resampling and flooding the logs. The browser already
    # applies echo cancellation + noise suppression on capture.
    denoiser = RNNoiseDenoiserProcessor(pipeline_sample_rate=SAMPLE_RATE, enabled=False)

    silence_detector = SilenceDetectorProcessor(
        silence_threshold_secs=15.0,
        medium_silence_threshold_secs=120.0,
        long_silence_threshold_secs=300.0,
    )

    call_mute = CallMuteProcessor()

    logger.info("Custom processors created | session_id={}", sid)

    # -- RTVI
    rtvi = RTVIProcessor()
    logger.info("RTVI processor created | session_id={}", sid)

    # -- LLM context (Louie by default; Toyota advisor for agent=automotive)
    if agent == "automotive":
        from agents.automotive.prompts import get_toyota_system_prompt

        system_prompt = get_toyota_system_prompt(language)
    else:
        system_prompt = get_system_prompt(language)

    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt}]
    )

    repeat_detector = RepeatDetectorProcessor(context=context)  # needs context

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                start=[vad_turn_start],
                stop=[smart_turn_stop, speech_timeout_stop],
            ),
            user_turn_stop_timeout=3.0,
        ),
        assistant_params=LLMAssistantAggregatorParams(),
    )
    logger.info("Context aggregators created | session_id={}", sid)

    context_sanitizer = ContextSanitizerProcessor(context=context)
    turn_reset = TurnResetProcessor(context=context)
    turn_logger = TurnLifecycleProcessor()

    # -- Pipeline
    pipeline = Pipeline(
        [
            transport.input(),  # raw audio from browser
            client_interrupt,  # browser {type: interrupt} -> InterruptionFrame
            audio_gate,  # drop echo while bot speaks, allow loud barge-in
            denoiser,  # RNNoise denoise before VAD sees audio
            vad,  # VAD -> user turn start + pipeline interruption
            turn_reset,  # drop truncated assistant from context on interrupt
            silence_detector,  # detect returning user after silence gap
            stt,  # audio -> TranscriptionFrame
            call_mute,  # drop frames while user is on a call
            repeat_detector,  # detect repeat intent, inject hint
            user_aggregator,  # turn detection + LLM context
            turn_logger,  # [Turn] lifecycle logs
            context_sanitizer,  # sanitize + trim before LLM
            pivot_detector,  # topic-change detection
            llm,  # text -> streaming response
            naturalizer,  # clean robotic phrases
            llm_empty_guard,  # inject fallback if LLM produced nothing
            tts,  # text -> audio chunks (Cartesia ~40ms TTFB)
            rtvi,  # RTVI events to browser
            assistant_aggregator,  # store reply in context
            transport.output(),  # stream audio to browser
        ]
    )
    logger.info("Pipeline assembled | session_id={}", sid)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )
    logger.info("Pipeline task created -- ready | session_id={}", sid)

    return transport, task, context
