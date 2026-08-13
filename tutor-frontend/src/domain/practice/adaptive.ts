/**
 * Adaptive practice view state and next-question selection.
 *
 * Selection is pure application logic: no LLM, no network, no async. The tutor
 * (backend) owns attempts and mastery; this module only mirrors that state for the
 * UI and picks which curriculum question to show next.
 */

import type { Difficulty, PracticeQuestion } from "@/domain/curriculum/types";
import type { AnswerEvaluation, MasteryLevel } from "@/domain/practice/evaluation";

export interface PracticeProgress {
  topicId: string | null;
  questionId: string | null;
  evaluation: AnswerEvaluation | null;
  attemptNumber: number;
  hintsUsed: number;
  hintLevel: number;
  difficulty: Difficulty;
  recommendedDifficulty: Difficulty;
  correct: number;
  partial: number;
  incorrect: number;
  consecutiveCorrect: number;
  consecutiveIncorrect: number;
  mastery: MasteryLevel;
  revealSolution: boolean;
}

export const IDLE_PRACTICE_PROGRESS: PracticeProgress = {
  topicId: null,
  questionId: null,
  evaluation: null,
  attemptNumber: 0,
  hintsUsed: 0,
  hintLevel: 0,
  difficulty: "easy",
  recommendedDifficulty: "easy",
  correct: 0,
  partial: 0,
  incorrect: 0,
  consecutiveCorrect: 0,
  consecutiveIncorrect: 0,
  mastery: "not_started",
  revealSolution: false,
};

const DIFFICULTY_RANK: Record<Difficulty, number> = {
  easy: 1,
  medium: 2,
  hard: 3,
};

const EVALUATIONS = new Set<AnswerEvaluation>([
  "correct",
  "partially_correct",
  "incorrect",
  "needs_hint",
  "hint_request",
  "conceptual_question",
  "ambiguous",
]);

const MASTERY_LEVELS = new Set<MasteryLevel>([
  "not_started",
  "learning",
  "developing",
  "strong",
  "mastered",
]);

function toDifficulty(value: unknown, fallback: Difficulty): Difficulty {
  return typeof value === "string" && value in DIFFICULTY_RANK
    ? (value as Difficulty)
    : fallback;
}

function toCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0;
}

/** Fold a `practice_progress` server event into the UI mirror. */
export function applyPracticeProgress(
  current: PracticeProgress,
  event: Record<string, unknown>,
): PracticeProgress {
  const evaluation = event.evaluation;
  const mastery = event.mastery;
  return {
    topicId: typeof event.topicId === "string" ? event.topicId : current.topicId,
    questionId:
      typeof event.questionId === "string" ? event.questionId : current.questionId,
    evaluation:
      typeof evaluation === "string" && EVALUATIONS.has(evaluation as AnswerEvaluation)
        ? (evaluation as AnswerEvaluation)
        : null,
    attemptNumber: toCount(event.attemptNumber),
    hintsUsed: toCount(event.hintsUsed),
    hintLevel: toCount(event.hintLevel),
    difficulty: toDifficulty(event.difficulty, current.difficulty),
    recommendedDifficulty: toDifficulty(
      event.recommendedDifficulty,
      current.recommendedDifficulty,
    ),
    correct: toCount(event.correct),
    partial: toCount(event.partial),
    incorrect: toCount(event.incorrect),
    consecutiveCorrect: toCount(event.consecutiveCorrect),
    consecutiveIncorrect: toCount(event.consecutiveIncorrect),
    mastery:
      typeof mastery === "string" && MASTERY_LEVELS.has(mastery as MasteryLevel)
        ? (mastery as MasteryLevel)
        : current.mastery,
    revealSolution: event.revealSolution === true,
  };
}

export interface NextQuestionOptions {
  questions: readonly PracticeQuestion[];
  /** Questions already shown this session, in order. */
  visitedQuestionIds: readonly string[];
  targetDifficulty: Difficulty;
}

/**
 * Pick the next question: closest to the target difficulty, never one already shown,
 * ties broken by curriculum order so the same session always behaves the same way.
 */
export function selectNextQuestion({
  questions,
  visitedQuestionIds,
  targetDifficulty,
}: NextQuestionOptions): PracticeQuestion | null {
  const visited = new Set(visitedQuestionIds);
  const remaining = questions.filter((question) => !visited.has(question.id));
  if (remaining.length === 0) return null;

  const target = DIFFICULTY_RANK[targetDifficulty];
  let best = remaining[0];
  let bestScore = Number.POSITIVE_INFINITY;
  for (const question of remaining) {
    const distance = Math.abs(DIFFICULTY_RANK[question.difficulty] - target);
    // Prefer the easier side of a tie: overshooting difficulty costs more than undershooting.
    const score = distance * 2 + (DIFFICULTY_RANK[question.difficulty] > target ? 1 : 0);
    if (score < bestScore) {
      best = question;
      bestScore = score;
    }
  }
  return best;
}

/** Short, honest progress line. Never a percentage. */
export function describeProgress(progress: PracticeProgress): string | null {
  const attempted = progress.correct + progress.partial + progress.incorrect;
  if (attempted === 0) return null;
  const retries = progress.incorrect + progress.partial;
  const solved = `${progress.correct} correct`;
  return retries > 0 ? `${solved} · ${retries} retry` : solved;
}

const MASTERY_COPY: Record<MasteryLevel, string | null> = {
  not_started: null,
  learning: "Working through it",
  developing: "Getting comfortable",
  strong: "Solid on this",
  mastered: "You've got this",
};

export function describeMastery(progress: PracticeProgress): string | null {
  return MASTERY_COPY[progress.mastery];
}
