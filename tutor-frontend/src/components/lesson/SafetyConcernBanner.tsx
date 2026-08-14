"use client";

import type { SafetyAlertView } from "@/lib/voice/safetyAlert";

const TELE_MANAS = "14416";

export function SafetyConcernBanner({
  safetyAlert,
}: {
  safetyAlert: SafetyAlertView;
}) {
  if (!safetyAlert.active) return null;

  const copy =
    safetyAlert.category === "harm_to_others"
      ? "If you or someone else might be in danger, step away and tell a trusted adult."
      : "If you are in danger right now, tell a parent, teacher, or another adult near you.";

  return (
    <div className="safety-concern" role="alert" aria-live="assertive">
      <p className="safety-concern-label">Safety check-in</p>
      <p className="safety-concern-copy">{copy}</p>
      <p className="safety-concern-copy">
        In India you can call Tele-MANAS at{" "}
        <a className="safety-concern-link" href={`tel:${TELE_MANAS}`}>
          {TELE_MANAS}
        </a>{" "}
        — 24 hours. You do not have to handle this alone.
      </p>
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
    <span className="safety-status-chip">
      Safety check-in · Tele-MANAS {TELE_MANAS}
    </span>
  );
}
