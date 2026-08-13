from loguru import logger

# -- Smart Turn
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
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

# -- Config and custom processors
from config import (
    CEREBRAS_API_KEY,
    CEREBRAS_API_KEY_2,
    GROQ_API_KEY,
    SARVAM_API_KEY,
    CARTESIA_API_KEY,
    LLM_MODEL,
    SAMPLE_RATE,
    DEFAULT_SESSION_LANGUAGE,
    LANGUAGE_MIN_CHARS,
    LANGUAGE_MIN_CONFIDENCE,
    LANGUAGE_CONFIRMATIONS,
    collect_pipeline_metrics,
)
from languages import (
    LANG_EN,
    display_name,
    normalize_session_lang,
    to_cartesia_language,
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
from processors.session_context import SessionContextProcessor, SessionContextStore
from processors.tutor_turn import TutorTurnProcessor
from processors.study_break import StudyBreakProcessor
from processors.text_input import TextInputProcessor
from tutor.breaks import BreakStore
from tutor.prompts import get_tutor_system_prompt
from processors.turn_reset import TurnResetProcessor
from processors.turn_logger import TurnLifecycleProcessor
from processors.silence_detector import SilenceDetectorProcessor
from processors.denoiser import RNNoiseDenoiserProcessor
from processors.transcription_dedup import TranscriptionDedupProcessor
from processors.llm_inference_dedup import LLMInferenceDedupProcessor
from processors.language_tracker import LanguageTrackerProcessor
from processors.tts_voice import TtsApplyVoiceProcessor, TtsVoiceProcessor
from processors.incidental_resume import (
    IncidentalResumeCaptureProcessor,
    IncidentalResumeGateProcessor,
    IncidentalResumeStore,
)
from voices import ALLOWED_TTS_VOICES, resolve_tts_voice_id


def get_system_prompt(language: str = LANG_EN) -> str:
    """Tutor persona system prompt (Phase 3). Kept name for call-site compatibility."""
    return get_tutor_system_prompt(language)


async def create_pipeline(
    websocket,
    language: str = "auto",
    session_id: str | None = None,
    voice_id: str | None = None,
):
    sid = session_id or "-"
    initial_lang = normalize_session_lang(language) or DEFAULT_SESSION_LANGUAGE or LANG_EN
    tts_voice_id = resolve_tts_voice_id(voice_id)
    logger.info(
        "Creating pipeline | session_id={} lang_param={} initial={} voice={} ({})",
        sid,
        language,
        display_name(initial_lang),
        tts_voice_id,
        ALLOWED_TTS_VOICES.get(tts_voice_id, "unknown"),
    )

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

    # -- STT (Sarvam saaras:v3 — language="unknown" = continuous auto-detect)
    stt = SarvamSTTService(
        api_key=SARVAM_API_KEY,
        model="saaras:v3",
        mode="transcribe",
        sample_rate=SAMPLE_RATE,
        keepalive_timeout=30.0,
        keepalive_interval=5.0,
        settings=SarvamSTTService.Settings(
            language="unknown",
            # Pipecat Silero VAD owns turn boundaries; Sarvam only transcribes + flush.
            vad_signals=False,
        ),
    )
    logger.info("STT service created | session_id={} auto_language=true", sid)

    # -- LLM (Cerebras primary, auto-failover on rate limits / errors)
    # A second Cerebras key is tried first: same provider, same model, separate
    # rate-limit bucket, so a "queue_exceeded" burst costs nothing extra.
    llm_fallbacks = []
    if CEREBRAS_API_KEY_2:
        llm_fallbacks.append(
            {
                "name": "Cerebras-2",
                "api_key": CEREBRAS_API_KEY_2,
                "base_url": "https://api.cerebras.ai/v1",
                "model": LLM_MODEL,
            }
        )
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
            max_completion_tokens=384,
            extra={"reasoning_effort": "low"},
        ),
    )
    logger.info(
        "LLM service created | session_id={} fallbacks={}",
        sid,
        [f["name"] for f in llm_fallbacks],
    )

    # -- TTS (Cartesia Sonic — language via Settings so mid-session updates work)
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        sample_rate=SAMPLE_RATE,
        voice_id=tts_voice_id,
        settings=CartesiaTTSService.Settings(
            voice=tts_voice_id,
            model="sonic-3.5",
            language=to_cartesia_language(initial_lang),
        ),
    )
    logger.info(
        "TTS service created | session_id={} language={} voice={} ({})",
        sid,
        display_name(initial_lang),
        tts_voice_id,
        ALLOWED_TTS_VOICES.get(tts_voice_id, "unknown"),
    )

    # -- Custom processors
    pivot_detector = PivotDetectorProcessor()
    llm_empty_guard = LLMEmptyGuardProcessor(timeout_secs=8.0)

    audio_gate = AudioGateProcessor(barge_in_rms=0.04, decay_secs=0.35)
    denoiser = RNNoiseDenoiserProcessor(pipeline_sample_rate=SAMPLE_RATE, enabled=False)

    silence_detector = SilenceDetectorProcessor(
        silence_threshold_secs=15.0,
        medium_silence_threshold_secs=120.0,
        long_silence_threshold_secs=300.0,
    )

    break_store = BreakStore()
    call_mute = CallMuteProcessor(should_skip_mute=break_store.should_skip_mute)
    transcription_dedup = TranscriptionDedupProcessor()
    llm_inference_dedup = LLMInferenceDedupProcessor()

    logger.info("Custom processors created | session_id={}", sid)

    # -- RTVI
    rtvi = RTVIProcessor()
    logger.info("RTVI processor created | session_id={}", sid)

    # -- LLM context (Lumina Class 10 tutor)
    system_prompt = get_system_prompt(initial_lang)
    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt}]
    )

    resume_store = IncidentalResumeStore()

    language_tracker = LanguageTrackerProcessor(
        context=context,
        session_id=sid,
        initial_language=initial_lang,
        min_chars=LANGUAGE_MIN_CHARS,
        min_confidence=LANGUAGE_MIN_CONFIDENCE,
        confirmations_needed=LANGUAGE_CONFIRMATIONS,
    )

    naturalizer = ResponseNaturalizerProcessor(
        add_starters=False,
        language=initial_lang,
        # Maths is rendered for the voice that speaks it: an Indic voice needs
        # variables as English letter names, an English voice does not.
        get_language=lambda: language_tracker.current_language,
        on_interrupt_leftover=resume_store.stash_unflushed,
    )

    repeat_detector = RepeatDetectorProcessor(context=context)

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                start=[vad_turn_start],
                stop=[smart_turn_stop],
            ),
            user_turn_stop_timeout=3.0,
        ),
        assistant_params=LLMAssistantAggregatorParams(),
    )
    logger.info(
        "LLM context created | session_id={} persona=Lumina Class 10 mathematics tutor",
        sid,
    )

    context_sanitizer = ContextSanitizerProcessor(context=context)
    turn_reset = TurnResetProcessor(context=context)
    turn_logger = TurnLifecycleProcessor()

    session_store = SessionContextStore()
    session_store.tts_voice_id = tts_voice_id
    session_context = SessionContextProcessor(
        store=session_store,
        llm_context=context,
        session_id=sid,
    )
    tutor_turn = TutorTurnProcessor(
        store=session_store,
        llm_context=context,
        session_id=sid,
        # LanguageTracker is upstream, so its active language is fresh for this
        # turn; the directive reasserts the reply language on every turn.
        get_language=lambda: language_tracker.current_language,
    )
    text_input = TextInputProcessor(
        store=session_store,
        llm_context=context,
        session_id=sid,
    )
    # After text_input / user aggregator so voice and typed turns share one
    # intercept. Not on the PCM / VAD / STT path.
    study_break = StudyBreakProcessor(
        store=break_store,
        llm_context=context,
        session_store=session_store,
        session_id=sid,
    )
    tts_voice = TtsVoiceProcessor(store=session_store, session_id=sid)
    tts_apply_voice = TtsApplyVoiceProcessor(store=session_store, session_id=sid)
    incidental_gate = IncidentalResumeGateProcessor(store=resume_store, context=context)
    incidental_capture = IncidentalResumeCaptureProcessor(store=resume_store)

    # -- Pipeline
    pipeline = Pipeline(
        [
            transport.input(),
            client_interrupt,
            tts_voice,
            session_context,
            audio_gate,
            denoiser,
            vad,
            turn_reset,
            silence_detector,
            stt,
            transcription_dedup,
            language_tracker,  # Sarvam lang + script → TTS + prompt steer
            call_mute,
            repeat_detector,
            incidental_gate,  # cough/noise → resume leftover TTS; real speech barges in
            user_aggregator,
            text_input,  # Typed chat → same LLMContext + Tutor Engine
            study_break,  # 1–5 min study break; LLM turns only, not audio
            tutor_turn,  # Tutor Engine: intent/mode → [TUTOR_TURN] directive
            turn_logger,
            context_sanitizer,
            llm_inference_dedup,
            pivot_detector,
            llm,
            naturalizer,
            incidental_capture,
            llm_empty_guard,
            tts_apply_voice,
            tts,
            rtvi,
            assistant_aggregator,
            transport.output(),
        ]
    )
    logger.info("Pipeline assembled | session_id={}", sid)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            allow_interruptions=True,
            enable_metrics=collect_pipeline_metrics(),
            enable_usage_metrics=collect_pipeline_metrics(),
        ),
        observers=[RTVIObserver(rtvi)],
    )
    logger.info("Pipeline task created -- ready | session_id={}", sid)

    return transport, task, context, session_store
