import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  evaluateAnswer,
  normalizeAnswer,
  stripConversationalPadding,
  type AnswerEvaluation,
} from "@/domain/practice/evaluation";

interface SharedCase {
  name: string;
  student: string;
  expected: string;
  accepted: string[];
  evaluation: AnswerEvaluation;
}

// Same table the Python tutor asserts, so voice and typed answers can never
// be scored differently. See shared/practice-answer-cases.json.
const sharedCases: SharedCase[] = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "..", "shared", "practice-answer-cases.json"),
    "utf-8",
  ),
).cases;

describe("shared practice evaluation contract", () => {
  it("loads the shared case table", () => {
    expect(sharedCases.length).toBeGreaterThan(10);
  });

  it.each(sharedCases)("$name", (testCase) => {
    expect(
      evaluateAnswer(testCase.student, testCase.expected, testCase.accepted)
        .evaluation,
    ).toBe(testCase.evaluation);
  });
});

describe("answer normalization", () => {
  it("folds notation students actually type", () => {
    expect(normalizeAnswer("  X² − 5x  ")).toBe("x^2 - 5x");
    expect(normalizeAnswer("6 × 7 ÷ 2.")).toBe("6 * 7 / 2");
  });

  it("drops lead-ins and trailing hedges", () => {
    expect(stripConversationalPadding("I think it's 2 and 3")).toBe("2 and 3");
    expect(stripConversationalPadding("2 and 3, but I'm not sure.")).toBe("2 and 3");
  });
});

describe("partial answers", () => {
  it("reports the value the student has not reached", () => {
    const result = evaluateAnswer("x is 3", "x = 3, -3");
    expect(result.evaluation).toBe("partially_correct");
    expect(result.missingValues).toEqual([-3]);
  });

  it("does not punish a student who shows working", () => {
    expect(
      evaluateAnswer("x squared is 9, so x is 3 or -3", "x = 3, -3").evaluation,
    ).toBe("correct");
  });
});
