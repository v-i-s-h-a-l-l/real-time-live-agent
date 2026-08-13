"use client";

export function LessonNav({
  progressLabel,
  canGoPrevious,
  canGoNext,
  nextLabel,
  nextDisabled,
  onPrevious,
  onNext,
}: {
  progressLabel: string;
  canGoPrevious: boolean;
  canGoNext: boolean;
  nextLabel: string;
  nextDisabled?: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav className="lesson-nav" aria-label="Lesson steps">
      <p className="lesson-progress" aria-live="polite">
        {progressLabel}
      </p>
      <div className="lesson-nav-actions">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onPrevious}
          disabled={!canGoPrevious}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onNext}
          disabled={!canGoNext || Boolean(nextDisabled)}
        >
          {nextLabel}
        </button>
      </div>
    </nav>
  );
}
