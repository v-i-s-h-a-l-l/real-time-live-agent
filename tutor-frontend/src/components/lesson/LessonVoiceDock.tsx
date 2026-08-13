"use client";

import type { MicState, VoiceConnectionState, VoiceTurnState } from "@/lib/voice/types";
import {
  TUTOR_VOICES,
  tutorVoiceLabel,
} from "@/lib/voice/voices";
import type { ConversationMessage } from "@/lib/voice/conversation";
import type { StudyBreakView } from "@/lib/voice/studyBreak";
import { BreakTimer } from "@/components/lesson/BreakTimer";
import { ConversationPanel } from "@/components/conversation/ConversationPanel";
import { StatusDot, type TutorLiveState } from "@/components/ui/StatusDot";
import { studentFacingError } from "@/lib/ui/studentFacingError";

function liveState(
  isActive: boolean,
  connectionState: VoiceConnectionState,
  turnState: VoiceTurnState,
): TutorLiveState {
  if (connectionState === "error") return "error";
  if (connectionState === "connecting") return "connecting";
  if (!isActive) return "offline";
  if (turnState === "listening") return "listening";
  if (turnState === "thinking") return "thinking";
  if (turnState === "speaking") return "speaking";
  return "ready";
}

export function LessonVoiceDock({
  lessonTitle,
  connectionState,
  turnState,
  micState,
  isActive,
  errorMessage,
  voiceId,
  messages,
  voiceResponsesEnabled,
  onVoiceResponsesChange,
  onSendText,
  onVoiceChange,
  onStart,
  onEnd,
  onClearError,
  studyBreak,
}: {
  lessonTitle: string;
  connectionState: VoiceConnectionState;
  turnState: VoiceTurnState;
  micState: MicState;
  isActive: boolean;
  errorMessage: string | null;
  voiceId: string;
  messages: ConversationMessage[];
  voiceResponsesEnabled: boolean;
  onVoiceResponsesChange: (enabled: boolean) => void;
  onSendText: (text: string) => boolean;
  onVoiceChange: (voiceId: string) => void;
  onStart: () => void;
  onEnd: () => void;
  onClearError: () => void;
  studyBreak: StudyBreakView;
}) {
  const connected = connectionState === "connected";
  const state = liveState(isActive, connectionState, turnState);
  const talkLabel =
    connectionState === "connecting" ? "Connecting…" : "Talk to tutor";

  return (
    <aside className="lesson-voice-dock" aria-label="AI Tutor">
      <div className="voice-dock-head">
        <div>
          <h2 className="voice-dock-title">AI Tutor</h2>
          <p className="voice-dock-context">
            Learning: <strong>{lessonTitle}</strong>
          </p>
        </div>
        <StatusDot state={state} />
      </div>

      <div className="voice-dock-toolbar">
        {!isActive ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onStart}
            disabled={connectionState === "connecting"}
          >
            {talkLabel}
          </button>
        ) : (
          <button type="button" className="btn btn-ghost" onClick={onEnd}>
            End
          </button>
        )}
        {micState === "error" ? (
          <span className="status-dot status-dot-error">Mic needs permission</span>
        ) : null}
        <label className="voice-dock-voice">
          <span>Voice</span>
          <select
            value={voiceId}
            onChange={(event) => onVoiceChange(event.target.value)}
            aria-label="Tutor voice"
          >
            {TUTOR_VOICES.map((voice) => (
              <option key={voice.id} value={voice.id}>
                {tutorVoiceLabel(voice)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {errorMessage ? (
        <div className="session-error" role="alert">
          <p>{studentFacingError(errorMessage)}</p>
          <button type="button" className="btn btn-ghost" onClick={onClearError}>
            Dismiss
          </button>
        </div>
      ) : null}

      <BreakTimer studyBreak={studyBreak} />

      <ConversationPanel
        messages={messages}
        disabled={!connected}
        disabledReason={
          connectionState === "connecting"
            ? "Connecting…"
            : "Talk to the tutor to start, then ask anything."
        }
        voiceLive={isActive && turnState === "listening"}
        sessionActive={isActive}
        onStartVoice={onStart}
        voiceConnecting={connectionState === "connecting"}
        voiceResponsesEnabled={voiceResponsesEnabled}
        onVoiceResponsesChange={onVoiceResponsesChange}
        onSend={onSendText}
        studyBreak={studyBreak}
      />
    </aside>
  );
}
