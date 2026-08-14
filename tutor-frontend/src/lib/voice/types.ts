/** Connection lifecycle for the voice WebSocket. */
export type VoiceConnectionState =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnecting"
  | "error";

/** High-level tutor turn state derived from RTVI + local playback. */
export type VoiceTurnState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking";

export type MicState = "off" | "requesting" | "on" | "error";

/** JSON object sent as a WebSocket control-message payload. */
export type JsonObject = Record<string, unknown>;

export interface VoiceAgentError {
  message: string;
  code?: string;
}

/** Server → client RTVI-style JSON envelope. */
export interface RtviMessage {
  type: string;
  data?: Record<string, unknown>;
  text?: string;
}

export interface VoiceAgentClientOptions {
  wsUrl: string;
  workletUrl?: string;
  lang?: string;
  /** Named barge-in timing (matches proven browser client). */
  interruptDebounceMs?: number;
  minBotSpeakingMsBeforeInterrupt?: number;
  micHealthCheckMs?: number;
}

export interface ConnectOptions {
  /** Extra WebSocket query params. */
  extraParams?: Record<string, string>;
  /** Curriculum / tutoring context sent immediately after socket open. */
  sessionContext?: JsonObject;
  /** Mint a short-lived engine token (Next.js /api/voice/session). */
  getSessionToken?: () => Promise<string | null>;
  /** Retry the socket after an unexpected drop. Default true. */
  enableReconnect?: boolean;
}

export interface VoiceAgentClientEvents {
  onConnectionChange?: (state: VoiceConnectionState) => void;
  onTurnChange?: (state: VoiceTurnState) => void;
  onMicChange?: (state: MicState) => void;
  onBotSpeakingChange?: (speaking: boolean) => void;
  onTranscription?: (text: string, meta?: { userId?: string }) => void;
  onAssistantText?: (delta: string) => void;
  onAssistantTextEnd?: () => void;
  onThinking?: () => void;
  onInterrupted?: () => void;
  onError?: (error: VoiceAgentError) => void;
  onBreakEvent?: (event: {
    type: string;
    spoken?: string;
    durationMinutes?: number | null;
    startedAt?: number | null;
    endsAt?: number | null;
  }) => void;
  onSafetyAlert?: (event: {
    type: string;
    category?: string;
    severity?: string;
    timestamp?: number | null;
    spoken?: string;
  }) => void;
  /** Adaptive practice state mirror. Shape is validated in the practice domain. */
  onPracticeProgress?: (event: Record<string, unknown>) => void;
}
