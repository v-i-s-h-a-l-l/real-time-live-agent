import Link from "next/link";

import type { Subject } from "@/domain/curriculum/types";
import { subjectPath } from "@/lib/routes";

export function SubjectCard({
  subject,
  chapterCount,
  classLabel,
  focus,
}: {
  subject: Subject;
  chapterCount: number;
  classLabel: string;
  focus: string;
}) {
  const chapterLabel =
    chapterCount === 1 ? "1 chapter" : `${chapterCount} chapters`;

  return (
    <Link
      href={subjectPath(subject.id)}
      className="subject-card subject-card-active"
    >
      <div className="subject-card-top">
        <p className="subject-kicker">{subject.name}</p>
        <span className="subject-status">Active</span>
      </div>
      <h3 className="subject-title">{subject.name}</h3>
      <p className="subject-meta">
        {classLabel}
        {chapterCount > 0 ? ` · ${chapterLabel}` : ""}
      </p>
      {focus ? <p className="subject-tagline">{focus}</p> : null}
      <span className="subject-cta">
        Open chapters
        <span className="home-cta-arrow" aria-hidden>
          →
        </span>
      </span>
    </Link>
  );
}
