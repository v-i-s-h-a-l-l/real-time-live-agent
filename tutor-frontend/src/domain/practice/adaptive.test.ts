import { describe, expect, it } from "vitest";

import type { PracticeQuestion } from "@/domain/curriculum/types";
import {
  applyPracticeProgress,
  describeMastery,
  describeProgress,
  IDLE_PRACTICE_PROGRESS,
  selectNextQuestion,
} from "@/domain/practice/adaptive";

function question(id: string, difficulty: PracticeQuestion["difficulty"]): PracticeQuestion {
  return {
    id,
    question: `Question ${id}`,
    difficulty,
    style: "direct",
    hints: ["hint"],
    expectedAnswer: "1",
    solution: ["step"],
  };
}

const bank = [
  question("q-easy-1", "easy"),
  question("q-medium-1", "medium"),
  question("q-medium-2", "medium"),
  question("q-hard-1", "hard"),
];

describe("next question selection", () => {
  it("picks the target difficulty when one is available", () => {
    expect(
      selectNextQuestion({
        questions: bank,
        visitedQuestionIds: ["q-easy-1"],
        targetDifficulty: "medium",
      })?.id,
    ).toBe("q-medium-1");
  });

  it("never repeats a question the student has already seen", () => {
    expect(
      selectNextQuestion({
        questions: bank,
        visitedQuestionIds: ["q-easy-1", "q-medium-1"],
        targetDifficulty: "medium",
      })?.id,
    ).toBe("q-medium-2");
  });

  it("eases off when the student is struggling", () => {
    expect(
      selectNextQuestion({
        questions: bank,
        visitedQuestionIds: ["q-hard-1"],
        targetDifficulty: "easy",
      })?.id,
    ).toBe("q-easy-1");
  });

  it("prefers an easier question over a harder one when the target is gone", () => {
    expect(
      selectNextQuestion({
        questions: bank,
        visitedQuestionIds: ["q-medium-1", "q-medium-2"],
        targetDifficulty: "medium",
      })?.id,
    ).toBe("q-easy-1");
  });

  it("returns null once every question has been attempted", () => {
    expect(
      selectNextQuestion({
        questions: bank,
        visitedQuestionIds: bank.map((item) => item.id),
        targetDifficulty: "medium",
      }),
    ).toBeNull();
  });
});

describe("practice progress mirror", () => {
  it("reads a well-formed server event", () => {
    const progress = applyPracticeProgress(IDLE_PRACTICE_PROGRESS, {
      topicId: "zeros-coefficients",
      questionId: "q-medium-1",
      evaluation: "correct",
      attemptNumber: 1,
      hintsUsed: 0,
      hintLevel: 0,
      difficulty: "medium",
      recommendedDifficulty: "hard",
      correct: 3,
      partial: 0,
      incorrect: 1,
      consecutiveCorrect: 2,
      consecutiveIncorrect: 0,
      mastery: "developing",
      revealSolution: false,
    });
    expect(progress.evaluation).toBe("correct");
    expect(progress.recommendedDifficulty).toBe("hard");
    expect(describeProgress(progress)).toBe("3 correct · 1 retry");
    expect(describeMastery(progress)).toBe("Getting comfortable");
  });

  it("ignores junk values rather than corrupting the UI", () => {
    const progress = applyPracticeProgress(IDLE_PRACTICE_PROGRESS, {
      evaluation: "totally-made-up",
      difficulty: 7,
      mastery: null,
      correct: -4,
    });
    expect(progress.evaluation).toBeNull();
    expect(progress.difficulty).toBe("easy");
    expect(progress.mastery).toBe("not_started");
    expect(progress.correct).toBe(0);
  });

  it("says nothing before the first attempt", () => {
    expect(describeProgress(IDLE_PRACTICE_PROGRESS)).toBeNull();
    expect(describeMastery(IDLE_PRACTICE_PROGRESS)).toBeNull();
  });
});
