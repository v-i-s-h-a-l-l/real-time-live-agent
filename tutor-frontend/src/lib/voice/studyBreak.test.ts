import { describe, expect, it } from "vitest";

import { ServerEvent } from "@/lib/voice/protocol";
import {
  applyStudyBreakEvent,
  formatCountdown,
  IDLE_STUDY_BREAK,
  remainingMs,
} from "@/lib/voice/studyBreak";

describe("study break remaining time", () => {
  it("computes remaining from the absolute end timestamp", () => {
    const endsAt = 1_000_000;
    expect(remainingMs(endsAt, 999_000)).toBe(1000);
    expect(remainingMs(endsAt, 1_000_000)).toBe(0);
    expect(remainingMs(endsAt, 1_000_500)).toBe(0);
  });

  it("formats a mm:ss countdown", () => {
    expect(formatCountdown(120_000)).toBe("02:00");
    expect(formatCountdown(61_000)).toBe("01:01");
    expect(formatCountdown(0)).toBe("00:00");
  });
});

describe("study break events", () => {
  it("starts from a break_started payload without stacking", () => {
    const started = applyStudyBreakEvent(IDLE_STUDY_BREAK, {
      type: ServerEvent.breakStarted,
      durationMinutes: 2,
      startedAt: 1_000,
      endsAt: 121_000,
      spoken: "Sure, take a two-minute break. I'll let you know when it's over.",
    });
    expect(started.phase).toBe("active");
    expect(started.durationMinutes).toBe(2);
    expect(started.endsAt).toBe(121_000);

    const again = applyStudyBreakEvent(started, {
      type: ServerEvent.breakStarted,
      durationMinutes: 2,
      startedAt: 1_000,
      endsAt: 121_000,
    });
    expect(again.endsAt).toBe(121_000);
    expect(again.phase).toBe("active");
  });

  it("returns to a completion state on break_ended", () => {
    const active = applyStudyBreakEvent(IDLE_STUDY_BREAK, {
      type: ServerEvent.breakStarted,
      durationMinutes: 2,
      startedAt: 1_000,
      endsAt: 121_000,
    });
    const ended = applyStudyBreakEvent(active, {
      type: ServerEvent.breakEnded,
      durationMinutes: 2,
      spoken: "Hey, your two-minute break is over. Ready to get back to the lesson?",
    });
    expect(ended.phase).toBe("ending");
    expect(ended.announcement).toContain("two-minute");
  });
});
