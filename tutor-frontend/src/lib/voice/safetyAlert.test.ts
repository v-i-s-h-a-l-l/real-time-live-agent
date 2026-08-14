import { describe, expect, it } from "vitest";

import {
  applySafetyAlertEvent,
  IDLE_SAFETY_ALERT,
} from "@/lib/voice/safetyAlert";

describe("safety alert view", () => {
  it("activates on a self-harm safety_alert", () => {
    const next = applySafetyAlertEvent(IDLE_SAFETY_ALERT, {
      type: "safety_alert",
      category: "self_harm",
      severity: "high",
      timestamp: 1_700_500,
    });
    expect(next).toEqual({
      active: true,
      category: "self_harm",
      timestamp: 1_700_500,
    });
  });

  it("keeps the banner for a later harm-to-others alert", () => {
    const first = applySafetyAlertEvent(IDLE_SAFETY_ALERT, {
      type: "safety_alert",
      category: "self_harm",
      timestamp: 1,
    });
    const next = applySafetyAlertEvent(first, {
      type: "safety_alert",
      category: "harm_to_others",
      timestamp: 2,
    });
    expect(next.active).toBe(true);
    expect(next.category).toBe("harm_to_others");
  });

  it("ignores unrelated events", () => {
    expect(
      applySafetyAlertEvent(IDLE_SAFETY_ALERT, { type: "break_started" }),
    ).toEqual(IDLE_SAFETY_ALERT);
  });
});
