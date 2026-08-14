"use client";

import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { TutorMarkdown } from "@/components/conversation/TutorMarkdown";
import { IconMic, IconSend } from "@/components/ui/Icons";
import { BreakStatusChip } from "@/components/lesson/BreakTimer";
import { SafetyStatusChip } from "@/components/lesson/SafetyConcernBanner";
import {
  isNearBottom,
  resolveScrollIntent,
  type ConversationMessage,
} from "@/lib/voice/conversation";
import type { StudyBreakView } from "@/lib/voice/studyBreak";
import type { SafetyAlertView } from "@/lib/voice/safetyAlert";

const STARTERS = [
  "Explain this concept",
  "Why does this work?",
  "Give me a hint",
];

// The list must be pinned before the browser paints the new content, or a
// streaming reply visibly jumps. On the server there is nothing to measure.
const useAnchorEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export function ConversationPanel({
  messages,
  disabled,
  disabledReason,
  voiceLive,
  sessionActive,
  onStartVoice,
  voiceConnecting,
  voiceResponsesEnabled,
  onVoiceResponsesChange,
  onSend,
  studyBreak,
  safetyAlert,
}: {
  messages: ConversationMessage[];
  disabled: boolean;
  disabledReason: string;
  voiceLive: boolean;
  sessionActive: boolean;
  onStartVoice: () => void;
  voiceConnecting: boolean;
  voiceResponsesEnabled: boolean;
  onVoiceResponsesChange: (enabled: boolean) => void;
  onSend: (text: string) => boolean;
  studyBreak: StudyBreakView;
  safetyAlert: SafetyAlertView;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const anchoredRef = useRef(true);
  const selfScrolling = useRef(false);
  const seenCount = useRef(messages.length);
  const [anchored, setAnchoredState] = useState(true);
  const [unread, setUnread] = useState(0);
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const speakId = useId();

  const setAnchored = useCallback((value: boolean) => {
    anchoredRef.current = value;
    setAnchoredState(value);
  }, []);

  const pinToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    const el = listRef.current;
    if (!el) return;
    if (behavior === "smooth") selfScrolling.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  const onScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const near = isNearBottom(el.scrollHeight - el.scrollTop - el.clientHeight);
    // A smooth scroll of ours passes through "not near the bottom" on the way
    // down; those frames are not the student choosing to read back.
    if (selfScrolling.current) {
      if (near) selfScrolling.current = false;
      return;
    }
    if (near === anchoredRef.current) return;
    setAnchored(near);
    if (near) setUnread(0);
  }, [setAnchored]);

  useAnchorEffect(() => {
    const arrived = messages.length - seenCount.current;
    seenCount.current = messages.length;
    const intent = resolveScrollIntent({
      arrived,
      latestRole: messages[messages.length - 1]?.role,
      anchored: anchoredRef.current,
    });

    if (intent === "pin") {
      setAnchored(true);
      setUnread(0);
      pinToBottom();
      return;
    }
    if (intent === "notify") setUnread((count) => count + arrived);
  }, [messages, pinToBottom, setAnchored]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content || typeof ResizeObserver === "undefined") return;
    // A streaming reply grows without a re-render (markdown reflow, fonts),
    // so follow the content height rather than only the message array.
    const observer = new ResizeObserver(() => {
      if (anchoredRef.current) pinToBottom();
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [pinToBottom]);

  const streaming = messages[messages.length - 1]?.status === "streaming";
  const showJump = !anchored && (unread > 0 || streaming);

  const jumpToLatest = () => {
    setAnchored(true);
    setUnread(0);
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    pinToBottom(reduceMotion ? "auto" : "smooth");
  };

  const submit = () => {
    const text = draft.trim();
    if (!text || disabled) return;
    const ok = onSend(text);
    if (ok) setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <section className="conversation-panel" aria-label="Tutor conversation">
      <header className="conversation-head">
        <h2>Conversation</h2>
        <div className="conversation-head-meta">
          <SafetyStatusChip safetyAlert={safetyAlert} />
          <BreakStatusChip studyBreak={studyBreak} />
          <label className="conversation-speak" htmlFor={speakId}>
            <input
              id={speakId}
              type="checkbox"
              checked={voiceResponsesEnabled}
              onChange={(event) => onVoiceResponsesChange(event.target.checked)}
            />
            Speak replies
          </label>
        </div>
      </header>

      <div className="conversation-body">
        <div
          ref={listRef}
          className="conversation-scroll"
          onScroll={onScroll}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
        >
          <div ref={contentRef}>
            {messages.length === 0 ? (
              <div className="transcript-empty">
                <p className="transcript-empty-title">
                  I’m here if you get stuck.
                </p>
                <p>Ask me about anything you’re learning.</p>
                <ul className="prompt-chips">
                  {STARTERS.map((prompt) => (
                    <li key={prompt}>
                      <button
                        type="button"
                        className="prompt-chip"
                        disabled={disabled}
                        onClick={() => {
                          if (disabled) return;
                          onSend(prompt);
                        }}
                      >
                        {prompt}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <ul className="transcript-list">
                {messages.map((entry) => (
                  <ConversationBubble key={entry.id} message={entry} />
                ))}
              </ul>
            )}
          </div>
        </div>

        {showJump ? (
          <button
            type="button"
            className="conversation-jump"
            onClick={jumpToLatest}
          >
            <span className="conversation-jump-dot" aria-hidden />
            {unread > 0
              ? `${unread} new message${unread > 1 ? "s" : ""}`
              : "Tutor is replying"}
          </button>
        ) : null}
      </div>

      <form
        className="conversation-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="sr-only" htmlFor={inputId}>
          Ask your tutor anything
        </label>
        <textarea
          id={inputId}
          rows={2}
          value={draft}
          disabled={disabled}
          placeholder={
            disabled ? disabledReason : "Ask your tutor anything…"
          }
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <button
          type="button"
          className={`btn btn-ghost btn-icon${voiceLive ? " is-live" : ""}`}
          onClick={onStartVoice}
          disabled={voiceConnecting || sessionActive}
          aria-label={
            voiceConnecting
              ? "Connecting"
              : voiceLive
                ? "Listening"
                : sessionActive
                  ? "Voice session active"
                  : "Talk to tutor"
          }
          title={
            sessionActive
              ? voiceLive
                ? "Listening"
                : "Voice session active"
              : "Talk to tutor"
          }
        >
          <IconMic />
        </button>
        <button
          type="submit"
          className="btn btn-primary btn-icon"
          disabled={disabled || !draft.trim()}
          aria-label="Send"
        >
          <IconSend />
        </button>
      </form>
    </section>
  );
}

const ConversationBubble = memo(function ConversationBubble({
  message,
}: {
  message: ConversationMessage;
}) {
  const label =
    message.role === "user"
      ? "You"
      : message.role === "assistant"
        ? "AI Tutor"
        : "Status";
  const source =
    message.role === "user" && message.source === "voice"
      ? "spoken"
      : message.role === "user" && message.source === "text"
        ? "typed"
        : null;
  return (
    <li
      className={`bubble role-${message.role}${message.status === "error" ? " is-error" : ""}`}
      aria-label={label}
    >
      <span className="bubble-role">
        {label}
        {source ? <span className="message-source">{source}</span> : null}
      </span>
      {message.role === "assistant" ? (
        <TutorMarkdown content={message.content} />
      ) : (
        <p>{message.content}</p>
      )}
    </li>
  );
});
