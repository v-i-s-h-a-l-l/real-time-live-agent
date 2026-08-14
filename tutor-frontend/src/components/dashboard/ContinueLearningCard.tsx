import Link from "next/link";

export function ContinueLearningCard({
  subjectName,
  chapterTitle,
  topicTitle,
  trail,
  href,
  chapterOrder,
}: {
  subjectName: string;
  chapterTitle: string;
  topicTitle: string;
  trail: string;
  href: string;
  chapterOrder: number;
}) {
  const marker = String(chapterOrder).padStart(2, "0");

  return (
    <Link href={href} className="continue-card">
      <span className="continue-accent" aria-hidden />
      <span className="continue-marker" aria-hidden>
        {marker}
      </span>
      <div className="continue-copy">
        <div className="continue-top">
          <p className="continue-kicker">Continue learning</p>
          <p className="continue-subject">{subjectName}</p>
        </div>
        <h2 className="continue-title">{topicTitle}</h2>
        <p className="continue-trail">{trail || chapterTitle}</p>
        <p className="continue-hint">Start with the first lesson in {subjectName}.</p>
      </div>
      <span className="continue-cta">
        Continue lesson
        <span className="home-cta-arrow" aria-hidden>
          →
        </span>
      </span>
    </Link>
  );
}
