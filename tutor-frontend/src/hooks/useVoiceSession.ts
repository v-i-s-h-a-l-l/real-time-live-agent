"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { toVoiceSessionPayload } from "@/domain/curriculum/sessionContext";
import type { TutorSessionContext } from "@/domain/curriculum/types";
import { VOICE_DEFAULT_LANG, VOICE_WS_URL } from "@/lib/config";
import { VoiceAgentClient } from "@/lib/voice/VoiceAgentClient";
import { mintVoiceToken } from "@/lib/voice/sessionToken";
import {
  emptyTranscript,
  reduceTranscript,
  type ConversationMessage,
  type TranscriptEvent,
} from "@/lib/voice/conversation";
import {
  applyPracticeProgress,
  IDLE_PRACTICE_PROGRESS,
  type PracticeProgress,
} from "@/domain/practice/adaptive";
import {
  applyStudyBreakEvent,
  IDLE_STUDY_BREAK,
  type StudyBreakView,
} from "@/lib/voice/studyBreak";
import {
  applySafetyAlertEvent,
  IDLE_SAFETY_ALERT,
  type SafetyAlertView,
} from "@/lib/voice/safetyAlert";
import type {
  JsonObject,
  MicState,
  VoiceConnectionState,
  VoiceTurnState,
} from "@/lib/voice/types";
import { DEFAULT_TUTOR_VOICE_ID } from "@/lib/voice/voices";

export interface VoiceSessionState {
  connectionState: VoiceConnectionState;
  turnState: VoiceTurnState;
  micState: MicState;
  messages: ConversationMessage[];
  errorMessage: string | null;
  isActive: boolean;
  voiceResponsesEnabled: boolean;
  studyBreak: StudyBreakView;
  safetyAlert: SafetyAlertView;
  practiceProgress: PracticeProgress;
}

export interface UseVoiceSessionResult extends VoiceSessionState {
  startSession: (
    tutorContext?: TutorSessionContext | null,
    voiceId?: string,
  ) => Promise<void>;
  endSession: () => void;
  clearError: () => void;
  /** Push active on-screen learning context when the visible unit changes. */
  updateLearningContext: (context: JsonObject) => void;
  /** Push tutor-only hints/solution for the current practice question. */
  updateTutorContext: (context: JsonObject) => void;
  /** Switch Cartesia TTS voice (connect-time and mid-session). */
  setTtsVoice: (voiceId: string) => void;
  sendText: (text: string) => boolean;
  setVoiceResponsesEnabled: (enabled: boolean) => void;
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * React bridge to VoiceAgentClient.
 * Owns one client instance per mount; tears down on unmount.
 */
export function useVoiceSession(): UseVoiceSessionResult {
  const clientRef = useRef<VoiceAgentClient | null>(null);
  const voiceResponsesRef = useRef(true);

  const [connectionState, setConnectionState] =
    useState<VoiceConnectionState>("idle");
  const [turnState, setTurnState] = useState<VoiceTurnState>("idle");
  const [micState, setMicState] = useState<MicState>("off");
  const [transcriptState, setTranscriptState] = useState(emptyTranscript);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [voiceResponsesEnabled, setVoiceResponsesEnabledState] = useState(true);
  const [studyBreak, setStudyBreak] = useState<StudyBreakView>(IDLE_STUDY_BREAK);
  const [safetyAlert, setSafetyAlert] =
    useState<SafetyAlertView>(IDLE_SAFETY_ALERT);
  const [practiceProgress, setPracticeProgress] = useState<PracticeProgress>(
    IDLE_PRACTICE_PROGRESS,
  );

  useEffect(() => {
    // A connect attempt, the mic health timer and in-flight socket events can
    // all land after the student navigates away; they must not touch state.
    let live = true;
    const ifLive =
      <T,>(update: (value: T) => void) =>
      (value: T) => {
        if (live) update(value);
      };
    const reduceIfLive = (event: TranscriptEvent) => {
      if (!live) return;
      setTranscriptState((prev) => reduceTranscript(prev, event));
    };

    const client = new VoiceAgentClient(
      {
        wsUrl: VOICE_WS_URL,
        lang: VOICE_DEFAULT_LANG,
      },
      {
        onConnectionChange: (state) => {
          ifLive(setConnectionState)(state);
          if (
            live &&
            (state === "idle" || state === "error" || state === "disconnecting")
          ) {
            setStudyBreak(IDLE_STUDY_BREAK);
            setSafetyAlert(IDLE_SAFETY_ALERT);
            setPracticeProgress(IDLE_PRACTICE_PROGRESS);
          }
        },
        onTurnChange: ifLive(setTurnState),
        onMicChange: ifLive(setMicState),
        onTranscription: (text, meta) => {
          reduceIfLive({
            type: "user-echo",
            content: text,
            userId: meta?.userId,
          });
        },
        onThinking: () => {
          reduceIfLive({ type: "assistant-start", id: makeId() });
        },
        onAssistantText: (delta) => {
          reduceIfLive({ type: "assistant-delta", delta });
        },
        onAssistantTextEnd: () => {
          reduceIfLive({ type: "assistant-end" });
        },
        onInterrupted: () => {
          reduceIfLive({ type: "interrupted" });
        },
        onError: (error) => {
          if (live) setErrorMessage(error.message);
        },
        onBreakEvent: (event) => {
          if (!live) return;
          setStudyBreak((prev) => applyStudyBreakEvent(prev, event));
          const spoken = event.spoken?.trim();
          if (spoken) {
            reduceIfLive({
              type: "assistant-complete",
              id: makeId(),
              content: spoken,
            });
          }
        },
        onSafetyAlert: (event) => {
          if (!live) return;
          setSafetyAlert((prev) => applySafetyAlertEvent(prev, event));
          const spoken = event.spoken?.trim();
          if (spoken) {
            reduceIfLive({
              type: "assistant-complete",
              id: makeId(),
              content: spoken,
            });
          }
        },
        onPracticeProgress: (event) => {
          if (!live) return;
          setPracticeProgress((prev) => applyPracticeProgress(prev, event));
        },
      },
    );

    clientRef.current = client;

    return () => {
      live = false;
      client.disconnect();
      clientRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (studyBreak.phase !== "ending" && studyBreak.phase !== "cancelled") {
      return;
    }
    const id = window.setTimeout(() => {
      setStudyBreak(IDLE_STUDY_BREAK);
    }, 2500);
    return () => window.clearTimeout(id);
  }, [studyBreak.phase]);

  const startSession = useCallback(
    async (tutorContext?: TutorSessionContext | null, voiceId?: string) => {
      setErrorMessage(null);
      setTranscriptState(emptyTranscript());
      setStudyBreak(IDLE_STUDY_BREAK);
      setSafetyAlert(IDLE_SAFETY_ALERT);
      setPracticeProgress(IDLE_PRACTICE_PROGRESS);
      const client = clientRef.current;
      if (!client) return;
      await client.connect({
        sessionContext: tutorContext
          ? toVoiceSessionPayload(tutorContext)
          : undefined,
        extraParams: { voice: voiceId || DEFAULT_TUTOR_VOICE_ID },
        getSessionToken: mintVoiceToken,
        enableReconnect: true,
      });
    },
    [],
  );

  const endSession = useCallback(() => {
    clientRef.current?.disconnect();
    setTurnState("idle");
    setMicState("off");
    setConnectionState("idle");
    setStudyBreak(IDLE_STUDY_BREAK);
    setSafetyAlert(IDLE_SAFETY_ALERT);
    setPracticeProgress(IDLE_PRACTICE_PROGRESS);
  }, []);

  const clearError = useCallback(() => setErrorMessage(null), []);

  const updateLearningContext = useCallback((context: JsonObject) => {
    clientRef.current?.sendLearningContext(context);
  }, []);

  const updateTutorContext = useCallback((context: JsonObject) => {
    clientRef.current?.sendTutorContext(context);
  }, []);

  const setTtsVoice = useCallback((voiceId: string) => {
    clientRef.current?.sendTtsVoice(voiceId);
  }, []);

  const setVoiceResponsesEnabled = useCallback((enabled: boolean) => {
    voiceResponsesRef.current = enabled;
    setVoiceResponsesEnabledState(enabled);
  }, []);

  const sendText = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return false;
    const client = clientRef.current;
    if (!client) return false;
    const id = makeId();
    const sent = client.sendTextInput(trimmed, {
      messageId: id,
      speak: voiceResponsesRef.current,
    });
    if (!sent) {
      setErrorMessage("Start voice to send a message.");
      return false;
    }
    setTranscriptState((prev) =>
      reduceTranscript(prev, {
        type: "user",
        id,
        content: trimmed,
        source: "text",
      }),
    );
    return true;
  }, []);

  const isActive =
    connectionState === "connected" || connectionState === "connecting";

  return {
    connectionState,
    turnState,
    micState,
    messages: transcriptState.messages,
    errorMessage,
    isActive,
    voiceResponsesEnabled,
    studyBreak,
    safetyAlert,
    practiceProgress,
    startSession,
    endSession,
    clearError,
    updateLearningContext,
    updateTutorContext,
    setTtsVoice,
    sendText,
    setVoiceResponsesEnabled,
  };
}
