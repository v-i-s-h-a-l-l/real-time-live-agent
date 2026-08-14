"use client";

import type { SafetyAlertView } from "@/lib/voice/safetyAlert";

export function SafetyConcernBanner({
  safetyAlert,
}: {
  safetyAlert: SafetyAlertView;
}) {
  if (!safetyAlert.active) return null;

  return (
    <div className="safety-concern" role="status" aria-live="polite">
      <p className="safety-concern-label">⚠ Safety concern detected</p>
    </div>
  );
}

export function SafetyStatusChip({
  safetyAlert,
}: {
  safetyAlert: SafetyAlertView;
}) {
  if (!safetyAlert.active) return null;

  return (
    <span className="safety-status-chip" aria-hidden="true">
      ⚠ Safety check-in
    </span>
  );
}
