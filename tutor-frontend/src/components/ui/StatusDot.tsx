export type TutorLiveState =
  | "offline"
  | "connecting"
  | "ready"
  | "listening"
  | "thinking"
  | "speaking"
  | "error";

const LABEL: Record<TutorLiveState, string> = {
  offline: "Off",
  connecting: "Connecting",
  ready: "Ready to help",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  error: "Needs attention",
};

export function StatusDot({
  state,
  label,
}: {
  state: TutorLiveState;
  label?: string;
}) {
  return (
    <span className={`status-dot status-dot-${state}`} role="status">
      <span className="status-dot-mark" aria-hidden />
      <span>{label ?? LABEL[state]}</span>
    </span>
  );
}
