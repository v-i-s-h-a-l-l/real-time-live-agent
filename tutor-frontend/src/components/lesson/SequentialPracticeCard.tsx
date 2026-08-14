"use client";

import { useState, type FormEvent } from "react";

import type { PracticeQuestion } from "@/domain/curriculum/types";
import { practiceHintCount } from "@/domain/curriculum/publicTopic";
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
  const [fetchedHints, setFetchedHints] = useState<string[]>([]);
  const [showSolution, setShowSolution] = useState(false);
  const [solutionSteps, setSolutionSteps] = useState<string[]>([]);
  const [expectedAnswer, setExpectedAnswer] = useState(question.expectedAnswer);
  const [busy, setBusy] = useState(false);

  const hintCount = practiceHintCount(question);
  const voiceGuarded = Boolean(onSubmitAnswer);
  const canRevealSolution =
    !voiceGuarded || Boolean(progress?.revealSolution);

  const tutorEvaluation =
    progress && progress.questionId === question.id ? progress.evaluation : null;
  const evaluation = tutorEvaluation ?? localEvaluation;
  const tone = evaluation ? (FEEDBACK_TONE[evaluation] ?? "idle") : "idle";
  const feedback = evaluation ? FEEDBACK[evaluation] : null;

  const topicProgress = progress ? describeProgress(progress) : null;
  const mastery = progress ? describeMastery(progress) : null;
  const visibleHints =
    question.hints.length > 0 ? question.hints : fetchedHints;

  function markAttempted(): void {
    onAttempted(true);
  }

  async function resolveEvaluation(value: string): Promise<AnswerEvaluation> {
    if (question.expectedAnswer) {
      return evaluateAnswer(
        value,
        question.expectedAnswer,
        question.acceptedAnswers ?? [],
      ).evaluation;
    }
    const response = await fetch("/api/practice/evaluate", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questionId: question.id, answer: value }),
    });
    if (!response.ok) return "ambiguous";
    const data = (await response.json()) as { evaluation?: AnswerEvaluation };
    return data.evaluation ?? "ambiguous";
  }

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!answer.trim() || busy) return;
    setBusy(true);
    try {
      setLocalEvaluation(await resolveEvaluation(answer));
      onSubmitAnswer?.(answer);
      markAttempted();
    } finally {
      setBusy(false);
    }
  }

  async function onHint(): Promise<void> {
    const next = Math.min(hintIndex + 1, Math.max(hintCount - 1, 0));
    if (question.hints.length === 0 && fetchedHints[next] == null) {
      const response = await fetch("/api/practice/hint", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questionId: question.id, index: next }),
      });
      if (response.ok) {
        const data = (await response.json()) as { hint?: string };
        if (data.hint) {
          setFetchedHints((prev) => {
            const copy = prev.slice();
            copy[next] = data.hint as string;
            return copy;
          });
        }
      }
    }
    setHintIndex(next);
    markAttempted();
  }

  async function onReveal(): Promise<void> {
    if (!canRevealSolution) return;
    if (!question.expectedAnswer || question.solution.length === 0) {
      const response = await fetch("/api/practice/solution", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questionId: question.id }),
      });
      if (response.ok) {
        const data = (await response.json()) as {
          solution?: string[];
          expectedAnswer?: string;
        };
        setSolutionSteps(data.solution ?? []);
        setExpectedAnswer(data.expectedAnswer ?? "");
      }
    } else {
      setSolutionSteps(question.solution);
      setExpectedAnswer(question.expectedAnswer);
    }
    setShowSolution(true);
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

      <form className="practice-form" onSubmit={(event) => void onSubmit(event)}>
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
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Submit
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void onHint()}
            disabled={hintCount <= 0 || (hintIndex >= hintCount - 1 && hintIndex >= 0)}
          >
            {hintIndex < 0 ? "Show hint" : "Next hint"}
          </button>
          {canRevealSolution ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => void onReveal()}
            >
              Show solution
            </button>
          ) : null}
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
            {visibleHints.slice(0, hintIndex + 1).map((hint) => (
              <li key={hint}>{hint}</li>
            ))}
          </ol>
        </div>
      ) : null}

      {showSolution ? (
        <div className="practice-solution">
          <h3>Solution</h3>
          <ol>
            {(solutionSteps.length > 0 ? solutionSteps : question.solution).map(
              (step) => (
                <li key={step}>{step}</li>
              ),
            )}
          </ol>
          {expectedAnswer ? (
            <p>
              <strong>Expected answer:</strong> {expectedAnswer}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
