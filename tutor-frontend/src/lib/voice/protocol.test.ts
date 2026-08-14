import { describe, expect, it } from "vitest";

import {
  ClientMessage,
  ServerEvent,
  TEXT_INPUT_USER_ID,
  WORKLET_USER_STARTED_SPEAKING,
} from "@/lib/voice/protocol";

/**
 * These strings are the contract with server/protocol.py and Pipecat's RTVI
 * processor. They are written out literally so that renaming a constant
 * cannot quietly change what goes on the wire.
 */
describe("websocket protocol", () => {
  it("sends the control messages the engine listens for", () => {
    expect(ClientMessage).toEqual({
      auth: "auth",
      interrupt: "interrupt",
      textInput: "text_input",
      ttsVoice: "tts_voice",
      sessionContext: "session_context",
      learningContext: "learning_context",
      tutorContext: "tutor_context",
    });
  });

  it("names the engine events the tutor UI reacts to", () => {
    expect(ServerEvent.authOk).toBe("auth_ok");
    expect(ServerEvent.botStartedSpeaking).toBe("bot-started-speaking");
    expect(ServerEvent.botStoppedSpeaking).toBe("bot-stopped-speaking");
    expect(ServerEvent.userTranscription).toBe("user-transcription");
    expect(ServerEvent.botLlmStarted).toBe("bot-llm-started");
    expect(ServerEvent.botLlmText).toBe("bot-llm-text");
    expect(ServerEvent.botLlmStopped).toBe("bot-llm-stopped");
    expect(ServerEvent.botInterrupted).toBe("bot-interrupted");
    expect(ServerEvent.breakStarted).toBe("break_started");
    expect(ServerEvent.breakEnded).toBe("break_ended");
    expect(ServerEvent.breakCancelled).toBe("break_cancelled");
    expect(ServerEvent.breakRequesting).toBe("break_requesting");
    expect(ServerEvent.breakMessage).toBe("break_message");
    expect(ServerEvent.safetyAlert).toBe("safety_alert");
    expect(ServerEvent.practiceProgress).toBe("practice_progress");
  });

  it("marks typed turns so they are not deduped as speech", () => {
    expect(TEXT_INPUT_USER_ID).toBe("text");
  });

  it("keeps worklet barge-in on the same literal as the engine event", () => {
    expect(WORKLET_USER_STARTED_SPEAKING).toBe("user-started-speaking");
    expect(WORKLET_USER_STARTED_SPEAKING).toBe(ServerEvent.userStartedSpeaking);
  });
});
