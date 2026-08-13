/** Study-break view model. Remaining time is always `endsAt - now`. */

export const MAX_BREAK_MINUTES = 5;
export const SUPPORTED_BREAK_MINUTES = [1, 2, 3, 4, 5] as const;

export type StudyBreakPhase =
  | "idle"
  | "requesting"
  | "active"
  | "ending"
  | "completed"
  | "cancelled";

export interface StudyBreakView {
  phase: StudyBreakPhase;
  durationMinutes: number | null;
  startedAt: number | null;
  endsAt: number | null;
  announcement: string;
}

export const IDLE_STUDY_BREAK: StudyBreakView = {
  phase: "idle",
  durationMinutes: null,
  startedAt: null,
  endsAt: null,
  announcement: "",
};

export interface StudyBreakEventPayload {
  type: string;
  spoken?: string;
  durationMinutes?: number | null;
  startedAt?: number | null;
  endsAt?: number | null;
}

export function remainingMs(endsAt: number | null, now: number): number {
  if (endsAt == null) return 0;
  return Math.max(0, endsAt - now);
}

export function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function durationLabel(minutes: number | null): string {
  if (minutes === 1) return "one-minute";
  if (minutes === 2) return "two-minute";
  if (minutes === 3) return "three-minute";
  if (minutes === 4) return "four-minute";
  if (minutes === 5) return "five-minute";
  return "study";
}

export function applyStudyBreakEvent(
  current: StudyBreakView,
  event: StudyBreakEventPayload,
): StudyBreakView {
  const spoken = (event.spoken || "").trim();
  switch (event.type) {
    case "break_requesting":
      return {
        phase: "requesting",
        durationMinutes: null,
        startedAt: null,
        endsAt: null,
        announcement: spoken || "Break requested. Choose a duration up to five minutes.",
      };
    case "break_started":
      return {
        phase: "active",
        durationMinutes: asMinutes(event.durationMinutes),
        startedAt: asEpochMs(event.startedAt),
        endsAt: asEpochMs(event.endsAt),
        announcement: spoken || `${capitalize(durationLabel(asMinutes(event.durationMinutes)))} break started.`,
      };
    case "break_ended":
      return {
        phase: "ending",
        durationMinutes: asMinutes(event.durationMinutes) ?? current.durationMinutes,
        startedAt: current.startedAt,
        endsAt: asEpochMs(event.endsAt) ?? current.endsAt,
        announcement: spoken || "Your break is over.",
      };
    case "break_cancelled":
      return {
        ...IDLE_STUDY_BREAK,
        phase: "cancelled",
        announcement: spoken || "Break cancelled.",
      };
    case "break_message":
      return {
        ...current,
        announcement: spoken || current.announcement,
      };
    default:
      return current;
  }
}

function asEpochMs(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  return Math.trunc(value);
}

function asMinutes(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  const minutes = Math.trunc(value);
  return minutes > 0 ? minutes : null;
}

function capitalize(text: string): string {
  if (!text) return text;
  return text.charAt(0).toUpperCase() + text.slice(1);
}
