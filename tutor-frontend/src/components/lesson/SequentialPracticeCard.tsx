"use client";

import { useState, type FormEvent } from "react";

import type { PracticeQuestion } from "@/domain/curriculum/types";
import {
  describeMastery,
  describeProgress,
  type PracticeProgress,
} from "@/domain/practice/adaptive";
import {
  evaluateAnswer,
  type AnswerEvaluation,
} from "@/domain/practice/evaluation";

/** Short, encouraging feedback. Never a score, never "evaluation: false". */
const FEEDBACK: Partial<Record<AnswerEvaluation, string>> = {
  correct: "That's right.",
  partially_correct: "Good approach — one piece is still missing.",
  incorrect: "Not quite — let's try that again.",
  needs_hint: "No worries. Here's a nudge.",
  hint_request: "Here's a nudge.",
};

const FEEDBACK_TONE: Partial<Record<AnswerEvaluation, string>> = {
  correct: "correct",
  partially_correct: "partial",
  incorrect: "incorrect",
};

export function SequentialPracticeCard({
  question,
  progressLabel,
  onAttempted,
  onSubmitAnswer,
  progress,
}: {
  question: PracticeQuestion;
  progressLabel: string;
  onAttempted: (attempted: boolean) => void;
  /** Hands the answer to the tutor so voice and typed attempts score identically. */
  onSubmitAnswer?: (answer: string) => boolean;
  progress?: PracticeProgress;
}) {
  const [answer, setAnswer] = useState("");
  const [localEvaluation, setLocalEvaluation] =
    useState<AnswerEvaluation | null>(null);
  const [hintIndex, setHintIndex] = useState(-1);
  const [showSolution, setShowSolution] = useState(false);

  // The tutor is authoritative once it has scored this question; the local
  // evaluator (same rules) covers the moment before the reply lands.
  const tutorEvaluation =
    progress && progress.questionId === question.id ? progress.evaluation : null;
  const evaluation = tutorEvaluation ?? localEvaluation;
  const tone = evaluation ? (FEEDBACK_TONE[evaluation] ?? "idle") : "idle";
  const feedback = evaluation ? FEEDBACK[evaluation] : null;

  const topicProgress = progress ? describeProgress(progress) : null;
  const mastery = progress ? describeMastery(progress) : null;

  function markAttempted(): void {
    onAttempted(true);
  }

  function onSubmit(event: FormEvent): void {
    event.preventDefault();
    if (!answer.trim()) return;
    setLocalEvaluation(
      evaluateAnswer(answer, question.expectedAnswer, question.acceptedAnswers ?? [])
        .evaluation,
    );
    onSubmitAnswer?.(answer);
    markAttempted();
  }

  return (
    <article className="lesson-practice" data-state={tone}>
      <div className="practice-card-top">
        <p className="lesson-unit-type">{progressLabel}</p>
        <div className="practice-card-meta">
          {topicProgress ? (
            <span className="practice-progress-chip" title="This topic, this session">
              {topicProgress}
            </span>
          ) : null}
          <span className={`pill difficulty-${question.difficulty}`}>
            {question.difficulty}
          </span>
        </div>
      </div>

      <h2 className="lesson-unit-title">{question.question}</h2>

      <form className="practice-form" onSubmit={onSubmit}>
        <label className="practice-label" htmlFor={`lesson-answer-${question.id}`}>
          Your answer
        </label>
        <textarea
          id={`lesson-answer-${question.id}`}
          className="practice-input"
          rows={3}
          value={answer}
          onChange={(event) => {
            setAnswer(event.target.value);
            if (localEvaluation) setLocalEvaluation(null);
          }}
          placeholder="Type your answer…"
        />
        <div className="practice-actions">
          <button type="submit" className="btn btn-primary">
            Submit
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setHintIndex((prev) =>
                Math.min(prev + 1, question.hints.length - 1),
              );
              markAttempted();
            }}
            disabled={hintIndex >= question.hints.length - 1 && hintIndex >= 0}
          >
            {hintIndex < 0 ? "Show hint" : "Next hint"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setShowSolution(true);
              markAttempted();
            }}
          >
            Show solution
          </button>
        </div>
      </form>

      {feedback ? (
        <p className={`practice-feedback practice-${tone}`} role="status">
          {feedback}
          {mastery && evaluation === "correct" ? (
            <span className="practice-mastery"> {mastery}.</span>
          ) : null}
        </p>
      ) : null}

      {hintIndex >= 0 ? (
        <div className="practice-hints">
          <h3>Hints</h3>
          <ol>
            {question.hints.slice(0, hintIndex + 1).map((hint) => (
              <li key={hint}>{hint}</li>
            ))}
          </ol>
        </div>
      ) : null}

      {showSolution ? (
        <div className="practice-solution">
          <h3>Solution</h3>
          <ol>
            {question.solution.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p>
            <strong>Expected answer:</strong> {question.expectedAnswer}
          </p>
        </div>
      ) : null}
    </article>
  );
}
