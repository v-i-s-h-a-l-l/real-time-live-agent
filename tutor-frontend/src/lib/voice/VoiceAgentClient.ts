import { AUDIO_WORKLET_URL } from "@/lib/config";
import {
  INTERRUPT_DEBOUNCE_MS,
  MIC_HEALTH_CHECK_MS,
  MIN_BOT_SPEAKING_MS_BEFORE_INTERRUPT,
  SAMPLE_RATE_HZ,
  SERVER_BARGE_IN_RESET_MS,
  TRANSCRIPT_DEDUPE_MS,
} from "@/lib/voice/constants";
import {
  ClientMessage,
  ServerEvent,
  TEXT_INPUT_USER_ID,
  WORKLET_USER_STARTED_SPEAKING,
} from "@/lib/voice/protocol";
import { DEFAULT_TUTOR_VOICE_ID } from "@/lib/voice/voices";
import type {
  ConnectOptions,
  JsonObject,
  MicState,
  RtviMessage,
  VoiceAgentClientEvents,
  VoiceAgentClientOptions,
  VoiceAgentError,
  VoiceConnectionState,
  VoiceTurnState,
} from "@/lib/voice/types";

function debugContext(event: string, payload: Record<string, unknown>): void {
  if (process.env.NODE_ENV === "production") return;
  console.info(`[${event}]`, payload);
}

function contextSummary(context: Record<string, unknown>): Record<string, unknown> {
  return {
    topicId: context.topicId,
    sectionId: context.sectionId,
    sectionTitle: context.sectionTitle,
    phase: context.phase,
    questionId: context.questionId,
    hasVisibleContent: Boolean(context.visibleContent),
    hasQuestion: Boolean(context.question),
  };
}

function optionalString(
  msg: RtviMessage,
  data: Record<string, unknown>,
  key: string,
): string | undefined {
  const raw = data[key] ?? (msg as unknown as Record<string, unknown>)[key];
  return typeof raw === "string" ? raw : undefined;
}

function optionalNumber(
  msg: RtviMessage,
  data: Record<string, unknown>,
  key: string,
): number | null | undefined {
  const raw = data[key] ?? (msg as unknown as Record<string, unknown>)[key];
  if (raw == null) return raw as null | undefined;
  const value = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(value) ? value : undefined;
}

/**
 * Browser voice transport for the existing FastAPI / Pipecat engine.
 *
 * Owns WebSocket, microphone capture (AudioWorklet), and TTS playback.
 * React must not call WebSocket/Audio APIs directly — use this class
 * (or the `useVoiceSession` hook that wraps it).
 */
export class VoiceAgentClient {
  private readonly wsUrl: string;
  private readonly workletUrl: string;
  private readonly lang: string;
  private readonly interruptDebounceMs: number;
  private readonly minBotSpeakingMsBeforeInterrupt: number;
  private readonly micHealthCheckMs: number;
  private readonly events: VoiceAgentClientEvents;

  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private silentGain: GainNode | null = null;

  private connectionState: VoiceConnectionState = "idle";
  private turnState: VoiceTurnState = "idle";
  private micState: MicState = "off";
  private connecting = false;
  private connected = false;

  private playQueue: ArrayBuffer[] = [];
  private isPlaying = false;
  private currentPlaybackSource: AudioBufferSourceNode | null = null;
  private flushGeneration = 0;
  private acceptBotAudio = false;
  private botIsSpeaking = false;
  private botStartedSpeakingAt = 0;
  private audioFramesSent = 0;

  private interruptDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  private serverBargeInResetTimer: ReturnType<typeof setTimeout> | null = null;
  private micHealthTimer: ReturnType<typeof setTimeout> | null = null;
  private serverHandledBargeIn = false;

  private lastTranscript = "";
  private lastTranscriptAt = 0;
  private suppressPlayback = false;
  private pendingSessionContext: JsonObject | null = null;
  private pendingLearningContext: JsonObject | null = null;
  private pendingTutorContext: JsonObject | null = null;
  private pendingTtsVoiceId: string = DEFAULT_TUTOR_VOICE_ID;

  constructor(options: VoiceAgentClientOptions, events: VoiceAgentClientEvents = {}) {
    this.wsUrl = options.wsUrl;
    this.workletUrl = options.workletUrl ?? AUDIO_WORKLET_URL;
    this.lang = options.lang ?? "auto";
    this.interruptDebounceMs =
      options.interruptDebounceMs ?? INTERRUPT_DEBOUNCE_MS;
    this.minBotSpeakingMsBeforeInterrupt =
      options.minBotSpeakingMsBeforeInterrupt ??
      MIN_BOT_SPEAKING_MS_BEFORE_INTERRUPT;
    this.micHealthCheckMs = options.micHealthCheckMs ?? MIC_HEALTH_CHECK_MS;
    this.events = events;
  }

  getConnectionState(): VoiceConnectionState {
    return this.connectionState;
  }

  getTurnState(): VoiceTurnState {
    return this.turnState;
  }

  getMicState(): MicState {
    return this.micState;
  }

  isSessionActive(): boolean {
    return this.connected || this.connecting;
  }

  /** Open mic + WebSocket session with the voice engine. */
  async connect(options: ConnectOptions = {}): Promise<void> {
    if (this.connected || this.connecting) {
      return;
    }

    this.connecting = true;
    this.setConnectionState("connecting");
    this.setMicState("requesting");
    this.pendingSessionContext = options.sessionContext ?? null;
    if (options.extraParams?.voice) {
      this.pendingTtsVoiceId = options.extraParams.voice;
    }

    this.stopAudioGraph();
    this.closeSocketOnly();

    try {
      await this.startMicrophone();
      await this.openWebSocket({
        voice: this.pendingTtsVoiceId,
        ...(options.extraParams ?? {}),
      });
    } catch (err) {
      this.connecting = false;
      this.setConnectionState("error");
      this.setMicState("error");
      this.emitError(this.mapConnectError(err));
      this.stopAudioGraph();
      this.closeSocketOnly();
    }
  }

  /** Send / update curriculum context on an open connection. */
  sendSessionContext(context: JsonObject): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.pendingSessionContext = context;
      return;
    }
    this.ws.send(
      JSON.stringify({
        type: ClientMessage.sessionContext,
        context,
      }),
    );
    debugContext("SESSION_CONTEXT_SENT", {
      topicId: context.topicId,
      topicTitle: context.topicTitle,
    });
  }

  /**
   * Push the currently visible lesson unit / practice question.
   * Queues until the WebSocket is open so the first slide is not dropped
   * while the session is still connecting.
   */
  sendLearningContext(context: JsonObject): void {
    this.pendingLearningContext = context;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      debugContext("LEARNING_CONTEXT_QUEUED", contextSummary(context));
      return;
    }
    this.ws.send(
      JSON.stringify({
        type: ClientMessage.learningContext,
        context,
      }),
    );
    this.pendingLearningContext = null;
    debugContext("LEARNING_CONTEXT_SENT", contextSummary(context));
  }

  /**
   * Push tutor-only practice context (hints/solution). Never send this as learning_context.
   */
  sendTutorContext(context: JsonObject): void {
    this.pendingTutorContext = context;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      debugContext("TUTOR_CONTEXT_QUEUED", contextSummary(context));
      return;
    }
    this.ws.send(
      JSON.stringify({
        type: ClientMessage.tutorContext,
        context,
      }),
    );
    this.pendingTutorContext = null;
    debugContext("TUTOR_CONTEXT_SENT", {
      questionId: context.questionId,
      phase: context.phase,
    });
  }

  /** Switch Cartesia TTS voice for the current session. */
  sendTtsVoice(voiceId: string): void {
    this.pendingTtsVoiceId = voiceId;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      debugContext("TTS_VOICE_QUEUED", { voiceId });
      return;
    }
    this.ws.send(
      JSON.stringify({
        type: ClientMessage.ttsVoice,
        voiceId,
      }),
    );
    debugContext("TTS_VOICE_SENT", { voiceId });
  }

  /** End session and release mic / AudioContext / WebSocket. */
  disconnect(): void {
    this.connecting = false;
    this.setConnectionState("disconnecting");
    this.closeSocketOnly();
    this.cleanup(false);
    this.setConnectionState("idle");
    this.setTurnState("idle");
    this.events.onConnectionChange?.("idle");
  }

  /** Explicit interrupt (also used by local barge-in). */
  interrupt(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: ClientMessage.interrupt }));
  }

  /**
   * Send a typed student message on the same voice WebSocket / Tutor Engine session.
   * Returns false if the socket is not open.
   */
  sendTextInput(text: string, options: { messageId?: string; speak?: boolean } = {}): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    const trimmed = text.trim();
    if (!trimmed) return false;
    this.suppressPlayback = options.speak === false;
    this.ws.send(
      JSON.stringify({
        type: ClientMessage.textInput,
        messageId: options.messageId ?? "",
        text: trimmed,
        speak: options.speak !== false,
      }),
    );
    return true;
  }

  private flushPendingContexts(): void {
    if (this.pendingSessionContext) {
      this.sendSessionContext(this.pendingSessionContext);
      this.pendingSessionContext = null;
    }
    if (this.pendingLearningContext) {
      this.sendLearningContext(this.pendingLearningContext);
    }
    if (this.pendingTutorContext) {
      this.sendTutorContext(this.pendingTutorContext);
    }
    this.sendTtsVoice(this.pendingTtsVoiceId);
  }

  // ── Internal: connection ─────────────────────────────────────────────

  private async startMicrophone(): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
    }
    this.setMicState("on");
  }

  private openWebSocket(extraParams: Record<string, string>): Promise<void> {
    return new Promise((resolve, reject) => {
      const base = this.wsUrl.split("?")[0];
      const params = new URLSearchParams({ lang: this.lang, ...extraParams });
      const url = `${base}?${params.toString()}`;

      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      this.ws = ws;

      let settled = false;

      ws.onopen = () => {
        void (async () => {
          try {
            this.connecting = false;
            this.connected = true;
            this.setConnectionState("connected");
            this.flushPendingContexts();
            await this.startAudioCapture();
            this.setTurnState("listening");
            this.startMicHealthCheck();
            settled = true;
            resolve();
          } catch (err) {
            settled = true;
            reject(err);
          }
        })();
      };

      ws.onmessage = (event) => this.handleServerMessage(event);

      ws.onclose = () => {
        this.connecting = false;
        this.cleanup(false);
        this.setConnectionState("idle");
        this.setTurnState("idle");
        if (!settled) {
          settled = true;
          reject(new Error("WebSocket closed before open"));
        }
      };

      ws.onerror = () => {
        this.connecting = false;
        if (!settled) {
          settled = true;
          reject(new Error("WebSocket error"));
        } else {
          this.emitError({ message: "WebSocket error" });
        }
      };
    });
  }

  private async startAudioCapture(): Promise<void> {
    this.audioContext = new AudioContext({ sampleRate: SAMPLE_RATE_HZ });
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    await this.audioContext.audioWorklet.addModule(this.workletUrl);

    if (!this.mediaStream) {
      throw new Error("Microphone stream missing");
    }

    this.micSource = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.workletNode = new AudioWorkletNode(this.audioContext, "audio-capture");
    this.silentGain = this.audioContext.createGain();
    this.silentGain.gain.value = 0;

    this.workletNode.port.onmessage = (event: MessageEvent) => {
      this.handleWorkletMessage(event.data);
    };

    this.micSource.connect(this.workletNode);
    this.workletNode.connect(this.silentGain);
    this.silentGain.connect(this.audioContext.destination);
  }

  private handleWorkletMessage(data: unknown): void {
    if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    if (
      data &&
      typeof data === "object" &&
      "type" in data &&
      (data as { type: string }).type === WORKLET_USER_STARTED_SPEAKING
    ) {
      const botActive =
        this.botIsSpeaking || this.isPlaying || this.playQueue.length > 0;
      if (botActive) {
        this.scheduleLocalBargeIn();
      }
      return;
    }

    if (!(data instanceof Float32Array)) {
      // AudioWorklet may transfer a plain Float32Array-like channel buffer.
      if (
        data &&
        typeof data === "object" &&
        "length" in data &&
        typeof (data as Float32Array).length === "number"
      ) {
        const float32 = data as Float32Array;
        this.sendAudio(this.float32ToPCM16(float32));
        return;
      }
      return;
    }

    this.sendAudio(this.float32ToPCM16(data));
  }

  sendAudio(pcm16: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(pcm16);
    this.audioFramesSent += 1;
  }

  // ── Internal: server events ──────────────────────────────────────────

  private handleServerMessage(event: MessageEvent): void {
    if (event.data instanceof ArrayBuffer) {
      this.enqueueAudio(event.data);
      return;
    }

    if (typeof event.data !== "string") return;

    try {
      const msg = JSON.parse(event.data) as RtviMessage;
      this.handleServerEvent(msg);
    } catch {
      // Ignore malformed control frames.
    }
  }

  handleServerEvent(msg: RtviMessage): void {
    const type = msg.type || "";
    const data = msg.data ?? {};

    switch (type) {
      case ServerEvent.botReady:
        break;

      case ServerEvent.botStartedSpeaking:
        this.botIsSpeaking = true;
        this.acceptBotAudio = true;
        this.botStartedSpeakingAt = Date.now();
        this.setTurnState("speaking");
        this.events.onBotSpeakingChange?.(true);
        break;

      case ServerEvent.botStoppedSpeaking:
        this.botIsSpeaking = false;
        this.suppressPlayback = false;
        if (this.connected) {
          this.setTurnState("listening");
        }
        this.events.onBotSpeakingChange?.(false);
        break;

      case ServerEvent.userStartedSpeaking:
        if (this.botIsSpeaking || this.isPlaying || this.playQueue.length > 0) {
          this.handleBargeInPlayback(false);
        }
        break;

      case ServerEvent.userTranscription: {
        const text = String(data.text ?? msg.text ?? "").trim();
        if (!text) break;
        const userId = String(data.user_id ?? data.userId ?? "");
        if (userId !== TEXT_INPUT_USER_ID) {
          const normalized = text.replace(/\s+/g, " ").toLowerCase();
          const now = Date.now();
          if (
            normalized === this.lastTranscript &&
            now - this.lastTranscriptAt < TRANSCRIPT_DEDUPE_MS
          ) {
            break;
          }
          this.lastTranscript = normalized;
          this.lastTranscriptAt = now;
        }
        this.events.onTranscription?.(text, { userId });
        break;
      }

      // The engine echoes the aggregated user turn; the transcript is already
      // built from user-transcription, so this would duplicate it.
      case ServerEvent.userLlmText:
        break;

      case ServerEvent.botLlmStarted:
        this.setTurnState("thinking");
        this.events.onThinking?.();
        break;

      case ServerEvent.botLlmText: {
        const delta = String(data.text ?? msg.text ?? "");
        if (delta) this.events.onAssistantText?.(delta);
        break;
      }

      case ServerEvent.botLlmStopped:
        this.events.onAssistantTextEnd?.();
        break;

      case ServerEvent.botInterrupted:
        this.suppressPlayback = false;
        this.events.onInterrupted?.();
        break;

      case ServerEvent.error:
      case ServerEvent.errorResponse:
        this.emitError({
          message: String(
            (data as { message?: string }).message ?? "Voice engine error",
          ),
        });
        break;

      case ServerEvent.breakStarted:
      case ServerEvent.breakEnded:
      case ServerEvent.breakCancelled:
      case ServerEvent.breakRequesting:
      case ServerEvent.breakMessage:
        this.events.onBreakEvent?.({
          type,
          spoken: optionalString(msg, data, "spoken"),
          durationMinutes: optionalNumber(msg, data, "durationMinutes"),
          startedAt: optionalNumber(msg, data, "startedAt"),
          endsAt: optionalNumber(msg, data, "endsAt"),
        });
        break;

      case ServerEvent.safetyAlert:
        this.events.onSafetyAlert?.({
          type,
          category: optionalString(msg, data, "category"),
          severity: optionalString(msg, data, "severity"),
          timestamp: optionalNumber(msg, data, "timestamp"),
          spoken: optionalString(msg, data, "spoken"),
        });
        break;

      case ServerEvent.practiceProgress:
        this.events.onPracticeProgress?.({
          ...(msg as unknown as Record<string, unknown>),
          ...data,
        });
        break;

      default:
        break;
    }
  }

  // ── Internal: barge-in + playback ────────────────────────────────────

  private scheduleLocalBargeIn(): void {
    this.clearInterruptDebounce();
    this.interruptDebounceTimer = setTimeout(() => {
      this.interruptDebounceTimer = null;
      if (!this.connected) return;

      const botActive =
        this.botIsSpeaking || this.isPlaying || this.playQueue.length > 0;
      if (!botActive) return;

      const msSinceBotStarted = Date.now() - this.botStartedSpeakingAt;
      if (msSinceBotStarted < this.minBotSpeakingMsBeforeInterrupt) {
        return;
      }

      this.handleBargeInPlayback(true);
    }, this.interruptDebounceMs);
  }

  private handleBargeInPlayback(sendServerInterrupt: boolean): void {
    const wasBotActive =
      this.botIsSpeaking || this.isPlaying || this.playQueue.length > 0;
    this.flushPlaybackQueue();
    this.botIsSpeaking = false;
    this.acceptBotAudio = false;
    this.events.onBotSpeakingChange?.(false);
    if (this.connected) {
      this.setTurnState("listening");
    }

    if (!sendServerInterrupt) {
      this.serverHandledBargeIn = true;
      this.clearServerBargeInReset();
      this.serverBargeInResetTimer = setTimeout(() => {
        this.serverHandledBargeIn = false;
        this.serverBargeInResetTimer = null;
      }, SERVER_BARGE_IN_RESET_MS);
      return;
    }

    if (
      wasBotActive &&
      !this.serverHandledBargeIn &&
      this.ws &&
      this.ws.readyState === WebSocket.OPEN
    ) {
      this.interrupt();
    }
  }

  private enqueueAudio(arrayBuffer: ArrayBuffer): void {
    if (this.suppressPlayback || !this.acceptBotAudio) return;
    this.playQueue.push(arrayBuffer);
    if (!this.isPlaying) {
      void this.playNext();
    }
  }

  private async playNext(): Promise<void> {
    const myGeneration = this.flushGeneration;

    if (this.playQueue.length === 0) {
      this.isPlaying = false;
      return;
    }

    this.isPlaying = true;
    const buf = this.playQueue.shift();
    if (!buf) {
      this.isPlaying = false;
      return;
    }

    try {
      if (!this.audioContext) return;
      if (this.flushGeneration !== myGeneration) return;

      const pcm16 = new Int16Array(buf);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768;
      }

      const audioBuffer = this.audioContext.createBuffer(
        1,
        float32.length,
        SAMPLE_RATE_HZ,
      );
      audioBuffer.getChannelData(0).set(float32);

      if (this.flushGeneration !== myGeneration) return;

      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);
      this.currentPlaybackSource = source;

      source.onended = () => {
        if (this.currentPlaybackSource === source) {
          this.currentPlaybackSource = null;
        }
        if (this.flushGeneration === myGeneration) {
          void this.playNext();
        }
      };

      source.start();
    } catch {
      if (this.flushGeneration === myGeneration) {
        void this.playNext();
      }
    }
  }

  private flushPlaybackQueue(): void {
    this.flushGeneration += 1;
    this.stopCurrentPlaybackSource();
    this.playQueue = [];
    this.isPlaying = false;
  }

  private stopCurrentPlaybackSource(): void {
    const src = this.currentPlaybackSource;
    if (!src) return;
    try {
      src.onended = null;
      src.stop(0);
    } catch {
      // Already stopped.
    }
    this.currentPlaybackSource = null;
  }

  // ── Internal: cleanup ────────────────────────────────────────────────

  private cleanup(resetWs: boolean): void {
    this.connected = false;
    this.connecting = false;
    this.botIsSpeaking = false;
    this.acceptBotAudio = false;
    this.suppressPlayback = false;
    this.lastTranscript = "";
    this.lastTranscriptAt = 0;
    this.clearInterruptDebounce();
    this.clearServerBargeInReset();
    this.serverHandledBargeIn = false;
    this.flushGeneration += 1;
    this.stopCurrentPlaybackSource();
    this.playQueue = [];
    this.isPlaying = false;
    this.audioFramesSent = 0;
    this.botStartedSpeakingAt = 0;
    this.stopAudioGraph();
    this.setMicState("off");

    if (resetWs) {
      this.closeSocketOnly();
    } else {
      this.ws = null;
    }
  }

  private stopAudioGraph(): void {
    if (this.micHealthTimer) {
      clearTimeout(this.micHealthTimer);
      this.micHealthTimer = null;
    }
    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      try {
        this.workletNode.disconnect();
      } catch {
        // ignore
      }
      this.workletNode = null;
    }
    if (this.micSource) {
      try {
        this.micSource.disconnect();
      } catch {
        // ignore
      }
      this.micSource = null;
    }
    if (this.silentGain) {
      try {
        this.silentGain.disconnect();
      } catch {
        // ignore
      }
      this.silentGain = null;
    }
    if (this.audioContext) {
      void this.audioContext.close().catch(() => undefined);
      this.audioContext = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }
  }

  private closeSocketOnly(): void {
    if (!this.ws) return;
    try {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
    } catch {
      // ignore
    }
    this.ws = null;
  }

  private startMicHealthCheck(): void {
    if (this.micHealthTimer) clearTimeout(this.micHealthTimer);
    this.audioFramesSent = 0;
    this.micHealthTimer = setTimeout(() => {
      if (!this.connected) return;
      if (this.audioFramesSent === 0) {
        this.emitError({ message: "No microphone audio detected." });
      }
    }, this.micHealthCheckMs);
  }

  private clearInterruptDebounce(): void {
    if (this.interruptDebounceTimer) {
      clearTimeout(this.interruptDebounceTimer);
      this.interruptDebounceTimer = null;
    }
  }

  private clearServerBargeInReset(): void {
    if (this.serverBargeInResetTimer) {
      clearTimeout(this.serverBargeInResetTimer);
      this.serverBargeInResetTimer = null;
    }
  }

  private float32ToPCM16(float32: Float32Array): ArrayBuffer {
    const buffer = new ArrayBuffer(float32.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buffer;
  }

  private setConnectionState(state: VoiceConnectionState): void {
    this.connectionState = state;
    this.events.onConnectionChange?.(state);
  }

  private setTurnState(state: VoiceTurnState): void {
    this.turnState = state;
    this.events.onTurnChange?.(state);
  }

  private setMicState(state: MicState): void {
    this.micState = state;
    this.events.onMicChange?.(state);
  }

  private emitError(error: VoiceAgentError): void {
    this.events.onError?.(error);
  }

  private mapConnectError(err: unknown): VoiceAgentError {
    const name =
      err && typeof err === "object" && "name" in err
        ? String((err as { name: string }).name)
        : "";
    const rawMessage =
      err instanceof Error ? err.message : "Could not access microphone";

    if (name === "NotFoundError" || /Requested device not found/i.test(rawMessage)) {
      return {
        message:
          "No microphone found. Enable a mic in system settings, allow browser access, then try again.",
        code: name || "NotFoundError",
      };
    }
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      return {
        message:
          "Microphone permission denied. Allow microphone access for this site, then refresh.",
        code: name,
      };
    }
    if (name === "NotReadableError" || name === "AbortError") {
      return {
        message:
          "Microphone is busy. Close other apps using the mic and try again.",
        code: name,
      };
    }
    return { message: rawMessage, code: name || undefined };
  }
}
