/** Safety-alert view model for the lesson UI. */

export type SafetyCategory = "self_harm" | "harm_to_others";

export interface SafetyAlertView {
  active: boolean;
  category: SafetyCategory | null;
  timestamp: number | null;
}

export const IDLE_SAFETY_ALERT: SafetyAlertView = {
  active: false,
  category: null,
  timestamp: null,
};

export interface SafetyAlertEventPayload {
  type: string;
  category?: string;
  severity?: string;
  timestamp?: number | null;
  spoken?: string;
}

function asCategory(value: string | undefined): SafetyCategory | null {
  if (value === "self_harm" || value === "harm_to_others") return value;
  return null;
}

export function applySafetyAlertEvent(
  current: SafetyAlertView,
  event: SafetyAlertEventPayload,
): SafetyAlertView {
  if (event.type !== "safety_alert") return current;
  const category = asCategory(event.category) ?? current.category;
  const timestamp =
    typeof event.timestamp === "number" && Number.isFinite(event.timestamp)
      ? event.timestamp
      : Date.now();
  return {
    active: true,
    category,
    timestamp,
  };
}
