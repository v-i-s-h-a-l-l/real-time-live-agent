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
from services.sarvam_stt import ReconnectingSarvamSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from services.tts_failover import CartesiaTTSWithFailover, build_fallback_tts

# -- Transport
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

# -- Config and custom processors
from config import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    LLM_PROVIDER,
    SARVAM_API_KEY,
    CARTESIA_API_KEY,
    CARTESIA_TTS_MODEL,
    LLM_MODEL,
    SAMPLE_RATE,
    DEFAULT_SESSION_LANGUAGE,
    LANGUAGE_MIN_CHARS,
    LANGUAGE_MIN_CONFIDENCE,
    LANGUAGE_CONFIRMATIONS,
    RNNOISE_ENABLED,
    VAD_START_SECS,
    VAD_STOP_SECS,
    STT_KEEPALIVE_TIMEOUT_SECS,
    STT_KEEPALIVE_INTERVAL_SECS,
    SARVAM_MIN_SPEECH_FRAMES,
    SARVAM_NEGATIVE_FRAMES_COUNT,
    SARVAM_NEGATIVE_FRAMES_WINDOW,
    SARVAM_PRE_SPEECH_PAD_FRAMES,
    AUDIO_GATE_DECAY_SECS,
    SILENCE_THRESHOLD_SECS,
    MEDIUM_SILENCE_THRESHOLD_SECS,
    LONG_SILENCE_THRESHOLD_SECS,
    USER_TURN_STOP_TIMEOUT_SECS,
    LLM_EMPTY_GUARD_TIMEOUT_SECS,
    collect_pipeline_metrics,
)
from languages import (
    LANG_EN,
    display_name,
    normalize_session_lang,
    to_cartesia_language,
)
from serializers.raw_pcm import RawPCMSerializer
from processors.reasoning_strip import ReasoningStripProcessor
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
from processors.safety import SafetyProcessor
from processors.text_input import TextInputProcessor
from tutor.breaks import BreakStore
from tutor.safety import SafetyStore
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

    # Silero VAD — barge-in + turn start. stop_secs must stay ≥ Sarvam's
    # negative_frames silence, or STT finalizes mid-pause and the aggregator
    # treats each fragment as a finished turn.
    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(
                confidence=0.6,
                start_secs=VAD_START_SECS,
                stop_secs=VAD_STOP_SECS,
                min_volume=0.7,
            )
        ),
    )
    client_interrupt = ClientInterruptProcessor()

    # -- STT (Sarvam saaras:v3 — language="unknown" = continuous auto-detect)
    stt = ReconnectingSarvamSTTService(
        api_key=SARVAM_API_KEY,
        model="saaras:v3",
        mode="transcribe",
        sample_rate=SAMPLE_RATE,
        keepalive_timeout=STT_KEEPALIVE_TIMEOUT_SECS,
        keepalive_interval=STT_KEEPALIVE_INTERVAL_SECS,
        settings=ReconnectingSarvamSTTService.Settings(
            language="unknown",
            # Pipecat Silero VAD owns turn boundaries (flush on VAD stop).
            # Keep vad_signals=False so Sarvam does not emit a second
            # UserStoppedSpeakingFrame stream. Fine-grained VAD still
            # controls when Sarvam emits a `data` transcript — defaults
            # (18 frames ≈ 0.58s) split slow speech; align with stop_secs.
            vad_signals=False,
            min_speech_frames=SARVAM_MIN_SPEECH_FRAMES,  # ~192ms before a segment starts
            negative_frames_count=SARVAM_NEGATIVE_FRAMES_COUNT,  # ~1.12s silence to end a segment
            negative_frames_window=SARVAM_NEGATIVE_FRAMES_WINDOW,  # lookback (~1.54s)
            pre_speech_pad_frames=SARVAM_PRE_SPEECH_PAD_FRAMES,  # ~512ms kept before speech onset
        ),
    )
    logger.info("STT service created | session_id={} auto_language=true", sid)

    # -- LLM (provider: openai | openrouter | gemini | groq)
    # Import the selected provider here so unused extras (Google Gemini,
    # etc.) are not required just to load the app or run tests.
    if LLM_PROVIDER == "openai":
        from services.openai_llm import OpenAILLMTutorService

        llm = OpenAILLMTutorService(
            api_key=OPENAI_API_KEY,
            settings=OpenAILLMTutorService.Settings(
                model=LLM_MODEL,
                max_completion_tokens=512,
            ),
        )
        logger.info(
            "LLM Service: OpenAI — model: {} | session_id={}",
            LLM_MODEL,
            sid,
        )
    elif LLM_PROVIDER == "openrouter":
        from services.openrouter_llm import OpenRouterLLMService

        llm = OpenRouterLLMService(
            api_key=OPENROUTER_API_KEY,
            settings=OpenRouterLLMService.Settings(
                model=LLM_MODEL,
                temperature=0.6,
                max_tokens=512,
                extra={"reasoning": {"enabled": True}},
            ),
        )
        logger.info(
            "LLM Service: OpenRouter — model: {} | session_id={}",
            LLM_MODEL,
            sid,
        )
    elif LLM_PROVIDER == "gemini":
        from services.gemini_llm import GeminiTutorLLMService

        llm = GeminiTutorLLMService(
            api_key=GEMINI_API_KEY,
            settings=GeminiTutorLLMService.Settings(
                model=LLM_MODEL,
                temperature=0.6,
                max_tokens=512,
                thinking=GeminiTutorLLMService.ThinkingConfig(
                    thinking_budget=0,
                    include_thoughts=False,
                ),
            ),
        )
        logger.info(
            "LLM Service: Gemini — model: {} | session_id={}",
            LLM_MODEL,
            sid,
        )
    else:
        from services.groq_llm import GroqReasoningLLMService

        llm = GroqReasoningLLMService(
            api_key=GROQ_API_KEY,
            settings=GroqReasoningLLMService.Settings(
                model=LLM_MODEL,
                temperature=0.6,
                max_completion_tokens=384,
                extra={
                    "reasoning_effort": "low",
                    "include_reasoning": False,
                },
            ),
        )
        logger.info(
            "LLM Service: Groq — model: {} | session_id={}",
            LLM_MODEL,
            sid,
        )

    # -- TTS (Cartesia Sonic — language via Settings so mid-session updates work)
    tts = CartesiaTTSWithFailover(
        api_key=CARTESIA_API_KEY,
        sample_rate=SAMPLE_RATE,
        voice_id=tts_voice_id,
        settings=CartesiaTTSService.Settings(
            voice=tts_voice_id,
            model=CARTESIA_TTS_MODEL,
            language=to_cartesia_language(initial_lang),
        ),
        fallback=build_fallback_tts(sample_rate=SAMPLE_RATE),
        session_id=sid,
    )
    logger.info(
        "TTS service created | session_id={} language={} voice={} ({})",
        sid,
        display_name(initial_lang),
        tts_voice_id,
        ALLOWED_TTS_VOICES.get(tts_voice_id, "unknown"),
    )

    # -- Custom processors
    reasoning_strip = ReasoningStripProcessor()
    pivot_detector = PivotDetectorProcessor()
    llm_empty_guard = LLMEmptyGuardProcessor(timeout_secs=LLM_EMPTY_GUARD_TIMEOUT_SECS)

    audio_gate = AudioGateProcessor(barge_in_rms=0.04, decay_secs=AUDIO_GATE_DECAY_SECS)
    denoiser = RNNoiseDenoiserProcessor(
        pipeline_sample_rate=SAMPLE_RATE,
        enabled=RNNOISE_ENABLED,
        session_id=sid,
    )

    silence_detector = SilenceDetectorProcessor(
        silence_threshold_secs=SILENCE_THRESHOLD_SECS,
        medium_silence_threshold_secs=MEDIUM_SILENCE_THRESHOLD_SECS,
        long_silence_threshold_secs=LONG_SILENCE_THRESHOLD_SECS,
    )

    break_store = BreakStore()
    safety_store = SafetyStore()
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
            user_turn_stop_timeout=USER_TURN_STOP_TIMEOUT_SECS,
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
        get_script=lambda: language_tracker.current_script,
    )
    text_input = TextInputProcessor(
        store=session_store,
        llm_context=context,
        session_id=sid,
        # Typed chat never hits STT, so the tracker must see these utterances too.
        observe_language=language_tracker.observe_utterance,
    )
    # After text_input / user aggregator so voice and typed turns share one
    # intercept. Not on the PCM / VAD / STT path. Safety runs first so a
    # crisis turn is never treated as study-break chatter.
    safety = SafetyProcessor(
        store=safety_store,
        llm_context=context,
        session_store=session_store,
        session_id=sid,
        get_language=lambda: language_tracker.current_language,
    )
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
            safety,  # Crisis intercept; regex only, not on the audio path
            study_break,  # 1–5 min study break; LLM turns only, not audio
            tutor_turn,  # Tutor Engine: intent/mode → [TUTOR_TURN] directive
            turn_logger,
            context_sanitizer,
            llm_inference_dedup,
            pivot_detector,
            llm,
            reasoning_strip,
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
