import Link from "next/link";

import type { Topic } from "@/domain/curriculum/types";
import { topicPath } from "@/lib/routes";

export function TopicList({
  subjectId,
  chapterId,
  topics,
}: {
  subjectId: string;
  chapterId: string;
  topics: Topic[];
}) {
  if (topics.length === 0) {
    return <p className="empty-state">No topics in this chapter yet.</p>;
  }

  return (
    <ul className="topic-list">
      {topics.map((topic) => (
        <li key={topic.id}>
          <Link
            href={topicPath(subjectId, chapterId, topic.id)}
            className="topic-row"
          >
            <div>
              <p className="topic-title">{topic.title}</p>
              <p className="topic-desc">{topic.shortDescription}</p>
            </div>
            <div className="topic-meta">
              <span className={`pill difficulty-${topic.difficulty}`}>
                {topic.difficulty}
              </span>
              <span>{topic.estimatedMinutes} min</span>
              <span>{topic.practiceQuestions.length} questions</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
