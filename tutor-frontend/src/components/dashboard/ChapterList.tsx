import Link from "next/link";

import type { Chapter } from "@/domain/curriculum/types";
import { chapterPath } from "@/lib/routes";

export function ChapterList({
  subjectId,
  chapters,
}: {
  subjectId: string;
  chapters: Chapter[];
}) {
  if (chapters.length === 0) {
    return (
      <section className="chapter-section">
        <div className="section-head">
          <h2>Chapters</h2>
          <p>No chapters are available for this subject yet.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="chapter-section" aria-labelledby="chapters-heading">
      <div className="section-head">
        <h2 id="chapters-heading">Chapters</h2>
        <p>Choose a chapter, then a topic, and learn with the tutor beside you.</p>
      </div>
      <ul className="chapter-list">
        {chapters.map((chapter) => (
          <li key={chapter.id}>
            <Link
              href={chapterPath(subjectId, chapter.id)}
              className="chapter-row"
            >
              <span>
                <span className="chapter-title">{chapter.title}</span>
                <span className="chapter-desc">{chapter.description}</span>
              </span>
              <span className="chapter-meta">
                {chapter.topicIds.length} topics
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
