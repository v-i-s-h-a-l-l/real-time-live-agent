"use client";

import { useEffect, useRef, useState } from "react";

import type { VoiceConnectionState } from "@/lib/voice/types";

export type VoiceConnectionNotice =
  | "lost"
  | "reconnecting"
  | "connected"
  | null;

export function resolveVoiceConnectionNotice(
  connectionState: VoiceConnectionState,
  isActive: boolean,
  hadConnected: boolean,
): VoiceConnectionNotice {
  if (!isActive) return null;
  if (connectionState === "error" && hadConnected) return "lost";
  if (connectionState === "connecting" && hadConnected) return "reconnecting";
  return null;
}

const COPY: Record<Exclude<VoiceConnectionNotice, null>, string> = {
  lost: "Voice connection lost",
  reconnecting: "Reconnecting…",
  connected: "Voice connected",
};

export function VoiceConnectionBanner({
  connectionState,
  isActive,
}: {
  connectionState: VoiceConnectionState;
  isActive: boolean;
}) {
  const hadConnectedRef = useRef(false);
  const [flashConnected, setFlashConnected] = useState(false);

  useEffect(() => {
    if (connectionState === "connected") {
      if (hadConnectedRef.current) {
        setFlashConnected(true);
        const timer = window.setTimeout(() => setFlashConnected(false), 2500);
        return () => window.clearTimeout(timer);
      }
      hadConnectedRef.current = true;
    }
    if (!isActive && connectionState === "idle") {
      hadConnectedRef.current = false;
      setFlashConnected(false);
    }
    return undefined;
  }, [connectionState, isActive]);

  const notice = flashConnected
    ? "connected"
    : resolveVoiceConnectionNotice(
        connectionState,
        isActive,
        hadConnectedRef.current,
      );

  if (!notice) return null;

  return (
    <div
      className={`voice-connection-banner voice-connection-banner-${notice}`}
      role="status"
      aria-live="polite"
    >
      {COPY[notice]}
    </div>
  );
}
