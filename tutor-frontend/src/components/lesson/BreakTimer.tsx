"use client";

import { useEffect, useState } from "react";

import {
  formatCountdown,
  remainingMs,
  type StudyBreakView,
} from "@/lib/voice/studyBreak";

export function BreakTimer({ studyBreak }: { studyBreak: StudyBreakView }) {
  const [now, setNow] = useState(() => Date.now());
  const ticking = studyBreak.phase === "active" && studyBreak.endsAt != null;

  useEffect(() => {
    if (!ticking) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [ticking, studyBreak.endsAt]);

  if (studyBreak.phase === "idle") return null;

  const remaining = remainingMs(studyBreak.endsAt, now);
  const clock = formatCountdown(
    studyBreak.phase === "active" ? remaining : 0,
  );
  const status =
    studyBreak.phase === "requesting"
      ? "How long? Up to five minutes"
      : studyBreak.phase === "active"
        ? "Break in progress"
        : studyBreak.phase === "ending"
          ? "Break over"
          : studyBreak.phase === "cancelled"
            ? "Welcome back"
            : "Break over";

  return (
    <div className="break-timer" role="status" aria-live="polite">
      <span className="sr-only">{studyBreak.announcement}</span>
      <div className="break-timer-card" aria-hidden="true">
        <p className="break-timer-label">☕ Break</p>
        {studyBreak.phase === "requesting" ? (
          <p className="break-timer-copy">Up to 5 minutes</p>
        ) : (
          <p className="break-timer-clock">{clock}</p>
        )}
        <p className="break-timer-status">{status}</p>
      </div>
    </div>
  );
}

export function BreakStatusChip({ studyBreak }: { studyBreak: StudyBreakView }) {
  const [now, setNow] = useState(() => Date.now());
  const ticking = studyBreak.phase === "active" && studyBreak.endsAt != null;

  useEffect(() => {
    if (!ticking) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [ticking, studyBreak.endsAt]);

  if (studyBreak.phase === "idle" || studyBreak.phase === "cancelled") {
    return null;
  }

  const clock = formatCountdown(remainingMs(studyBreak.endsAt, now));
  const label =
    studyBreak.phase === "requesting"
      ? "☕ Break · up to 5 min"
      : studyBreak.phase === "active"
        ? `☕ Break · ${clock}`
        : "☕ Break over";

  return (
    <span className="break-status-chip" aria-hidden="true">
      {label}
    </span>
  );
}
