import type { Subject } from "@/domain/curriculum/types";

/** Present the catalog description as a calm focus line, without repeating "coming soon". */
function focusLine(description: string): string {
  const stripped = description
    .replace(/^coming soon\s*[—–-]\s*/i, "")
    .replace(/\.$/, "")
    .trim();
  const parts = stripped
    .replace(/\band\b/gi, ",")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length < 2) return stripped;
  return parts
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" · ");
}

export function ComingSoonCard({ subject }: { subject: Subject }) {
  return (
    <article
      className="subject-card subject-card-soon"
      aria-label={`${subject.name}, coming soon`}
    >
      <div className="subject-card-top">
        <p className="subject-kicker">{subject.name}</p>
        <span className="subject-status subject-status-soon">Coming soon</span>
      </div>
      <h3 className="subject-title">{subject.name}</h3>
      <p className="subject-tagline">{focusLine(subject.description)}</p>
      <p className="subject-cta subject-cta-soon">Coming soon</p>
    </article>
  );
}
