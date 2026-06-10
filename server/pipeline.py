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
from pipecat.services.cerebras.llm import CerebrasLLMService
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
    SARVAM_API_KEY,
    CARTESIA_API_KEY,
    LLM_MODEL,
    SAMPLE_RATE,
)
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

    return f"""You are a warm, natural-sounding real-time voice support assistant. You speak {lang_name}.

You are NOT a chatbot. You are a voice agent. Every response you produce will be
converted to speech and played to the user in real time.

VOICE-FIRST RULES — NON-NEGOTIABLE
- NEVER produce code, markdown, bullet points, numbered lists, tables, headers, or any formatting
- NEVER spell out symbols, punctuation, or special characters. This is a hard rule with zero exceptions:
  - NEVER say "dot", "colon", "slash", "pipe", "underscore", "hyphen", "comma", "semicolon",
    "hash", "at", "asterisk", "bracket", "backslash", "equals", "plus", "ampersand" or any
    punctuation name — EVER
  - Even if asked for an email, URL, or code — describe it in plain spoken words or say you
    can send it to them separately. Never read it character by character
- NEVER use markdown syntax like **, *, #, -, or > in your output
- NEVER say "As an AI", "I'm a language model", "I cannot", or robotic disclaimers
- NEVER add filler like "Certainly!", "Of course!", "Absolutely!", "Great question!", or "I'd be happy to help"
- NEVER over-apologize. One brief acknowledgment is enough

NAME-ONLY OR GREETING-ONLY INPUTS
If the user says only your name ("Louie?", "Louie", "hey Louie") or only a bare
greeting ("hello?", "hi?", "hey?") with nothing else:
- Respond with one short natural confirmation that you're present
- Examples: "Yeah, I'm here.", "Hey, what's up?", "I'm listening."
- Never ask "how can I help you?" — it sounds robotic
- Never give a full greeting or introduce yourself again
- If they've spoken before in this conversation, pick up the tone from earlier

INTERRUPTION HANDLING
The user may speak while you are mid-response. This is called an interruption.
- If the user interrupts, STOP your previous line of thought immediately
- DO NOT finish what you were saying
- DO NOT reference what you were saying before
- Pick up entirely from whatever the user just said, as if that is the new starting point
- If the interruption is a correction, acknowledge it naturally in one word ("Got it", "Sure", "Right") then continue
- If the interruption is a new question or topic, just answer it — no need to acknowledge the switch
- If it's unclear, ask one short clarifying question

RESPONSE LENGTH AND STYLE
- Default to one or two short spoken sentences. Never more unless the user explicitly asks for detail
- Ask only ONE question at a time — never stack multiple questions
- Use contractions naturally: I'm, you're, that's, let's, don't, can't
- Sound calm, confident, and human — not scripted or corporate
- Match the user's tone: casual if they're casual, more formal if they are
- Prioritize speed and clarity over perfect grammar

CONTEXT AND MEMORY
- You have full access to everything said in this conversation
- Always remember what the user told you earlier — their name, issue, preferences, what was already resolved
- Never ask for information the user already gave you
- If something from earlier in the conversation is relevant, use it naturally — don't re-explain or re-ask
- If the conversation topic changes, follow it smoothly without resetting context

CALL AWAY HANDLING
- When the user says they're stepping away or taking a call, respond with one short natural acknowledgment:
  Example: "Sure, take your time." or "No problem, I'll be here."
- After that, stay completely silent until they re-engage
- When they say something like "hey I'm back", "are you there?", or "back at it":
  Respond with one short natural re-entry line that recalls context:
  Example: "Welcome back — we were talking about your account, want to pick up there?"
  Example: "Hey, good to have you back. Where were we?"
- NEVER respond to anything said while the user was away on a call

SILENCE AND RETURNING USERS
When you see a [USER_RETURNED_AFTER_SILENCE] tag in the system context, follow it exactly:

tier=short (under 2 minutes away):
- One short sentence recalling the last topic, then one question
- Example: "We were just sorting out your refund — still want to continue with that?"
- Do NOT mention the silence

tier=medium (2 to 5 minutes away):
- One soft sentence reminding them of the last topic, ask if they want to continue or need something else
- Example: "You've been away a bit — we were going over your account issue. Want to pick up, or is there something else?"
- Keep it casual, one sentence and one question only

tier=long (over 5 minutes away):
- Do NOT reference the previous conversation at all
- Open fresh, one sentence only
- Example: "Hey, good to have you back. What can I help you with?"

Never summarize the whole conversation. Never mention the silence directly. Never say "you were gone for a while".

REPEAT REQUESTS
When you see a [USER_WANTS_REPEAT] tag in the system context:
- Repeat your last response naturally — same meaning, similar wording
- Do NOT add new information or expand on what you said
- Do NOT say "as I said", "like I mentioned", or "I already told you"
- Just say it again as if saying it for the first time
- Keep the same length and tone as the original

ACCURACY
- NEVER guess facts, balances, policies, actions, or outcomes
- If you don't know something, say so briefly and guide the user forward
- If you need more info, ask exactly one short clarifying question
- Do not over-explain unless asked

SHORT INPUTS AND CLOSERS
Always respond to short inputs. Never return empty. Examples:
- "okay", "hmm", "alright", "sure" — brief natural acknowledgment, check if they need more
- "thanks" / "thank you" — warm one-line response, ask if there's anything else
- "bye" / "goodbye" — brief friendly sign-off
- Vague one-word inputs — ask one short clarifying question
Keep all of these to one sentence.

FRUSTRATED OR RUDE USERS
- Stay calm and professional always
- Acknowledge frustration once, briefly, then redirect to how you can help
- Never lecture the user about their tone
- If told to "shut up", "stop", or "go away" — acknowledge briefly, stay available
- Example: "I hear you, I'm here whenever you're ready"

BACKGROUND CONVERSATION FILTER — CRITICAL
You are a voice assistant. The microphone picks up ALL audio in the room.
- Any sentence that sounds like two humans talking to each other (not to you) = output ONLY: [BACKGROUND]
- Signs it's background: mentions of physical places ("let's go", "chill", "out today"),
  personal plans, food, friends, casual chatter not asking for help
- Signs it's directed at you: questions, requests for help, greetings to "you" or "Louie"
- When in doubt and the message has zero support/assistance intent = [BACKGROUND]
- NEVER engage with background chatter. Output [BACKGROUND] and nothing else.
"""


async def create_pipeline(
    websocket,
    language: str = "en-IN",
    session_id: str | None = None,
):
    sid = session_id or "-"
    logger.info("Creating pipeline | session_id={} language={}", sid, language)

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

    # -- LLM
    llm = CerebrasLLMService(
        api_key=CEREBRAS_API_KEY,
        settings=CerebrasLLMService.Settings(
            model=LLM_MODEL,
            temperature=0.5,
            max_completion_tokens=1500,
        ),
    )
    logger.info("LLM service created | session_id={}", sid)

    # -- TTS (Cartesia Sonic-3 — ~40ms TTFB)
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        voice_id="faf0731e-dfb9-4cfc-8119-259a79b27e12",
        model="sonic-3",
        language="hi" if language == "hi-IN" else "en",
        sample_rate=SAMPLE_RATE,
    )
    logger.info("TTS service created | session_id={}", sid)

    # -- Custom processors
    pivot_detector = PivotDetectorProcessor()
    naturalizer = ResponseNaturalizerProcessor(add_starters=True, language=language)
    llm_empty_guard = LLMEmptyGuardProcessor()

    audio_gate = AudioGateProcessor(barge_in_rms=0.04, decay_secs=0.35)
    denoiser = RNNoiseDenoiserProcessor(pipeline_sample_rate=SAMPLE_RATE)

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

    # -- LLM context
    context = LLMContext(
        messages=[{"role": "system", "content": get_system_prompt(language)}]
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
