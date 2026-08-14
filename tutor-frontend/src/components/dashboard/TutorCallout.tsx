import Link from "next/link";

export function TutorCallout({ href }: { href: string }) {
  return (
    <section className="tutor-callout" aria-labelledby="tutor-callout-heading">
      <div className="tutor-callout-copy">
        <h2 id="tutor-callout-heading" className="tutor-callout-kicker">
          <span className="tutor-callout-mark" aria-hidden>
            ✦
          </span>
          Meet your tutor
        </h2>
        <p className="tutor-callout-lead">Ask about whatever you&apos;re learning.</p>
        <p className="tutor-callout-body">
          Lumina knows what&apos;s on your screen, so you can ask questions,
          request an explanation, or work through a problem without leaving your
          lesson.
        </p>
        <Link href={href} className="tutor-callout-cta">
          Start a conversation
          <span className="home-cta-arrow" aria-hidden>
            →
          </span>
        </Link>
      </div>
      <div className="tutor-thread" aria-hidden>
        <p className="tutor-line tutor-line-student">Can you explain this?</p>
        <p className="tutor-line tutor-line-tutor">
          Sure. Let&apos;s break it down step by step.
        </p>
      </div>
    </section>
  );
}
