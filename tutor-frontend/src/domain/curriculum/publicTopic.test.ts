import { describe, expect, it } from "vitest";

import { toPublicTopic } from "@/domain/curriculum/publicTopic";
import type { Topic } from "@/domain/curriculum/types";
import { stableStringify } from "@/lib/server/signing";

const topic: Topic = {
  id: "t1",
  chapterId: "c1",
  title: "Quadratic Formula",
  shortDescription: "Solve quadratics",
  learningObjectives: ["Apply the formula"],
  prerequisites: [],
  conceptNotes: [],
  keyPoints: [],
  formulas: [],
  examples: [],
  commonMistakes: [],
  hints: ["study hint"],
  practiceQuestions: [
    {
      id: "q1",
      question: "Solve x^2 - 5x + 6 = 0",
      difficulty: "easy",
      style: "direct",
      hints: ["Factor"],
      expectedAnswer: "x = 2, 3",
      solution: ["(x-2)(x-3)=0"],
    },
  ],
  difficulty: "easy",
  relatedTopicIds: [],
  estimatedMinutes: 20,
};

describe("public topic DTO", () => {
  it("strips practice answers and keeps a hint count", () => {
    const publicTopic = toPublicTopic(topic);
    const question = publicTopic.practiceQuestions[0];
    expect(question.expectedAnswer).toBe("");
    expect(question.solution).toEqual([]);
    expect(question.hints).toEqual([]);
    expect(question.hintCount).toBe(1);
    expect(question.question).toContain("x^2");
  });
});

describe("stableStringify", () => {
  it("matches Python canonical JSON key order", () => {
    expect(stableStringify({ b: 1, a: 2 })).toBe('{"a":2,"b":1}');
  });
});
