import Link from "next/link";

import type { Subject } from "@/domain/curriculum/types";
import { subjectPath } from "@/lib/routes";

export function SubjectCard({ subject }: { subject: Subject }) {
  if (!subject.available) {
    return (
      <article className="subject-card subject-card-disabled">
        <p className="subject-kicker">Subject</p>
        <h2 className="subject-title">{subject.name}</h2>
        <p className="subject-tagline">{subject.description}</p>
        <span className="subject-badge">Soon</span>
      </article>
    );
  }

  return (
    <Link href={subjectPath(subject.id)} className="subject-card subject-card-active">
      <p className="subject-kicker">Subject</p>
      <h2 className="subject-title">{subject.name}</h2>
      <p className="subject-tagline">{subject.description}</p>
      <span className="subject-cta">Open chapters →</span>
    </Link>
  );
}
