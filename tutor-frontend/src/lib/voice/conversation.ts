/** Conversation transcript model shared by voice STT and typed chat. */

import { TEXT_INPUT_USER_ID } from "@/lib/voice/protocol";

export type ConversationRole = "user" | "assistant" | "system";
export type ConversationSource = "voice" | "text" | "system";
export type ConversationStatus = "streaming" | "complete" | "error";

export interface ConversationMessage {
  id: string;
  role: ConversationRole;
  content: string;
  timestamp: number;
  source: ConversationSource;
  status: ConversationStatus;
}

export const SCROLL_STICK_THRESHOLD_PX = 72;

export function isNearBottom(
  distanceFromBottom: number,
  threshold = SCROLL_STICK_THRESHOLD_PX,
): boolean {
  return distanceFromBottom <= threshold;
}

/**
 * What the message list should do when the transcript changes.
 *
 * "pin" follows the latest message, "notify" leaves the reading position
 * alone and flags unread arrivals, "hold" does nothing at all.
 */
export type ScrollIntent = "pin" | "notify" | "hold";

export function resolveScrollIntent({
  arrived,
  latestRole,
  anchored,
}: {
  arrived: number;
  latestRole: ConversationRole | undefined;
  anchored: boolean;
}): ScrollIntent {
  // Sending a message is a deliberate act: always return to the latest turn.
  if (arrived > 0 && latestRole === "user") return "pin";
  if (anchored) return "pin";
  return arrived > 0 ? "notify" : "hold";
}

export type TranscriptEvent =
  | { type: "reset" }
  | {
      type: "user";
      id: string;
      content: string;
      source: "voice" | "text";
    }
  | { type: "user-echo"; content: string; userId?: string }
  | { type: "assistant-start"; id: string }
  | { type: "assistant-delta"; delta: string }
  | { type: "assistant-end" }
  | { type: "assistant-complete"; id: string; content: string }
  | { type: "assistant-error"; message: string }
  | { type: "interrupted" };

export interface TranscriptState {
  messages: ConversationMessage[];
  streamingId: string | null;
}

export function emptyTranscript(): TranscriptState {
  return { messages: [], streamingId: null };
}

function normalize(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

export function reduceTranscript(
  state: TranscriptState,
  event: TranscriptEvent,
): TranscriptState {
  switch (event.type) {
    case "reset":
      return emptyTranscript();

    case "user": {
      const message: ConversationMessage = {
        id: event.id,
        role: "user",
        content: event.content,
        timestamp: Date.now(),
        source: event.source,
        status: "complete",
      };
      return {
        ...state,
        messages: [...state.messages, message],
      };
    }

    case "user-echo": {
      if (event.userId === TEXT_INPUT_USER_ID) {
        return state;
      }
      const incoming = normalize(event.content);
      if (!incoming) return state;
      const lastUser = [...state.messages].reverse().find((m) => m.role === "user");
      if (
        lastUser &&
        lastUser.source === "text" &&
        normalize(lastUser.content) === incoming
      ) {
        return state;
      }
      const message: ConversationMessage = {
        id: `stt-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        role: "user",
        content: event.content,
        timestamp: Date.now(),
        source: "voice",
        status: "complete",
      };
      return { ...state, messages: [...state.messages, message] };
    }

    case "assistant-start": {
      if (state.streamingId) {
        return state;
      }
      const lastUser = [...state.messages].reverse().find((m) => m.role === "user");
      const source: ConversationSource =
        lastUser?.source === "text" ? "text" : "voice";
      const message: ConversationMessage = {
        id: event.id,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        source,
        status: "streaming",
      };
      return {
        streamingId: event.id,
        messages: [...state.messages, message],
      };
    }

    case "assistant-delta": {
      const delta = event.delta;
      if (!delta) return state;
      let streamingId = state.streamingId;
      let messages = state.messages;
      if (!streamingId) {
        streamingId = `asst-${Date.now()}`;
        messages = [
          ...messages,
          {
            id: streamingId,
            role: "assistant",
            content: "",
            timestamp: Date.now(),
            source: [...messages].reverse().find((m) => m.role === "user")?.source === "text"
              ? "text"
              : "voice",
            status: "streaming",
          },
        ];
      }
      messages = messages.map((msg) =>
        msg.id === streamingId
          ? { ...msg, content: msg.content + delta, status: "streaming" as const }
          : msg,
      );
      return { messages, streamingId };
    }

    case "assistant-end": {
      if (!state.streamingId) return state;
      const id = state.streamingId;
      return {
        streamingId: null,
        messages: state.messages.map((msg) =>
          msg.id === id
            ? {
                ...msg,
                status: msg.content.trim() ? "complete" : "error",
                content: msg.content.trim()
                  ? msg.content
                  : "The tutor did not return a reply. Try again.",
              }
            : msg,
        ),
      };
    }

    case "assistant-complete": {
      const content = event.content.trim();
      if (!content) return state;
      const last = state.messages[state.messages.length - 1];
      if (
        last?.role === "assistant" &&
        last.content.trim() === content
      ) {
        return state;
      }
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: event.id,
            role: "assistant",
            content,
            timestamp: Date.now(),
            source: "voice",
            status: "complete",
          },
        ],
      };
    }

    case "assistant-error": {
      const id = state.streamingId;
      if (id) {
        return {
          streamingId: null,
          messages: state.messages.map((msg) =>
            msg.id === id
              ? { ...msg, status: "error", content: event.message }
              : msg,
          ),
        };
      }
      return {
        streamingId: null,
        messages: [
          ...state.messages,
          {
            id: `err-${Date.now()}`,
            role: "system",
            content: event.message,
            timestamp: Date.now(),
            source: "system",
            status: "error",
          },
        ],
      };
    }

    case "interrupted": {
      if (!state.streamingId) return state;
      const id = state.streamingId;
      return {
        streamingId: null,
        messages: state.messages.map((msg) =>
          msg.id === id ? { ...msg, status: "complete" as const } : msg,
        ),
      };
    }

    default:
      return state;
  }
}
