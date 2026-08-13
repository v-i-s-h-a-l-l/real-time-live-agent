/**
 * Wire protocol for the browser <-> voice engine WebSocket.
 *
 * The socket carries raw PCM-16 audio as binary frames and JSON control
 * messages as text frames. These values are the contract with the FastAPI
 * engine and are mirrored in `server/protocol.py`; changing one without the
 * other breaks the session.
 */

/** Control messages the browser sends. Handled one-per-processor server side. */
export const ClientMessage = {
  interrupt: "interrupt",
  textInput: "text_input",
  ttsVoice: "tts_voice",
  sessionContext: "session_context",
  learningContext: "learning_context",
  tutorContext: "tutor_context",
} as const;

export type ClientMessageType =
  (typeof ClientMessage)[keyof typeof ClientMessage];

/**
 * Events the engine sends on the voice WebSocket.
 * RTVI events come from Pipecat; `break_*` events are application messages
 * on the same socket.
 */
export const ServerEvent = {
  botReady: "bot-ready",
  botStartedSpeaking: "bot-started-speaking",
  botStoppedSpeaking: "bot-stopped-speaking",
  userStartedSpeaking: "user-started-speaking",
  userTranscription: "user-transcription",
  userLlmText: "user-llm-text",
  botLlmStarted: "bot-llm-started",
  botLlmText: "bot-llm-text",
  botLlmStopped: "bot-llm-stopped",
  botInterrupted: "bot-interrupted",
  error: "error",
  errorResponse: "error-response",
  breakStarted: "break_started",
  breakEnded: "break_ended",
  breakCancelled: "break_cancelled",
  breakRequesting: "break_requesting",
  breakMessage: "break_message",
  practiceProgress: "practice_progress",
} as const;

export type ServerEventType = (typeof ServerEvent)[keyof typeof ServerEvent];

/**
 * Speaker id the engine attaches to transcriptions that came from typed
 * input rather than the microphone, so they are not deduped as speech.
 */
export const TEXT_INPUT_USER_ID = "text";

/**
 * Message the audio worklet posts to the main thread on local barge-in.
 * Same literal as ServerEvent.userStartedSpeaking, but a different channel:
 * worklet → page, not engine → page. Keep the strings in lockstep.
 */
export const WORKLET_USER_STARTED_SPEAKING = ServerEvent.userStartedSpeaking;
