import { describe, expect, it } from "vitest";

import {
  buildTutorSessionContext,
  CurriculumLookupError,
  toVoiceSessionPayload,
} from "@/domain/curriculum/sessionContext";
import type { CurriculumCatalog, Topic } from "@/domain/curriculum/types";
import { validateCurriculumCatalog } from "@/domain/curriculum/validateContent";
import { answersMatch, normalizeAnswer } from "@/domain/practice/answerMatching";
import { CurriculumService } from "@/services/curriculum/CurriculumService";

const service = new CurriculumService();

describe("CurriculumService hierarchy", () => {
  it("returns Class 10 subjects", () => {
    const subjects = service.getSubjects("class-10");
    expect(subjects.map((s) => s.id)).toContain("mathematics");
  });

  it("returns ordered mathematics chapters", () => {
    expect(service.getChapters("mathematics").map((c) => c.id)).toEqual([
      "real-numbers",
      "polynomials",
      "pair-of-linear-equations",
      "quadratic-equations",
    ]);
  });

  it("returns topics for a chapter", () => {
    const topics = service.getTopics("quadratic-equations");
    expect(topics.map((t) => t.id)).toContain("quadratic-formula");
  });

  it("handles unknown ids", () => {
    expect(service.getTopic("nope")).toBeNull();
    expect(service.getTopicContent("nope")).toBeNull();
    expect(service.getQuestion("nope")).toBeNull();
    expect(service.getTopics("nope")).toEqual([]);
  });
});

describe("Topic learning content", () => {
  it("loads rich topic content for quadratic formula", () => {
    const content = service.getTopicContent("quadratic-formula");
    expect(content).not.toBeNull();
    expect(content!.conceptNotes.length).toBeGreaterThanOrEqual(3);
    expect(content!.examples.length).toBeGreaterThanOrEqual(3);
    expect(content!.practiceQuestions.length).toBeGreaterThanOrEqual(5);
    expect(content!.commonMistakes.length).toBeGreaterThanOrEqual(2);
    expect(content!.keyPoints.length).toBeGreaterThanOrEqual(3);
  });

  it("returns examples and practice questions via dedicated APIs", () => {
    expect(service.getExamples("discriminant").length).toBeGreaterThan(0);
    expect(service.getPracticeQuestions("factorisation-quadratic").length).toBeGreaterThanOrEqual(3);
  });

  it("looks up questions, hints, and solutions by id", () => {
    const questions = service.getPracticeQuestions("quadratic-formula");
    const first = questions[0];
    expect(first).toBeDefined();
    expect(service.getQuestion(first.id)?.id).toBe(first.id);
    expect(service.getHint(first.id, 0)).toBe(first.hints[0]);
    expect(service.getHint(first.id, 99)).toBeNull();
    expect(service.getSolution(first.id)).toEqual(first.solution);
    expect(service.getTopicIdForQuestion(first.id)).toBe("quadratic-formula");
  });

  it("builds session context from topic content", () => {
    const ctx = service.createSessionContext("quadratic-formula");
    expect(ctx.topicDescription.length).toBeGreaterThan(10);
    expect(toVoiceSessionPayload(ctx).topicId).toBe("quadratic-formula");
  });

  it("throws on unknown topic for session context", () => {
    expect(() =>
      buildTutorSessionContext(service.getCatalogForTests(), "missing-topic"),
    ).toThrow(CurriculumLookupError);
  });
});

describe("content validation", () => {
  it("accepts the production catalog", () => {
    const result = service.validateContent();
    expect(result.ok).toBe(true);
    expect(result.issues).toEqual([]);
  });

  it("detects duplicate topic ids", () => {
    const catalog = structuredClone(service.getCatalogForTests()) as CurriculumCatalog;
    const topic = catalog.topics[0];
    catalog.topics.push({ ...topic, id: topic.id });
    const result = validateCurriculumCatalog(catalog);
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.message.includes("duplicate topic"))).toBe(true);
  });

  it("detects duplicate practice question ids", () => {
    const catalog = structuredClone(service.getCatalogForTests()) as CurriculumCatalog;
    const topic = catalog.topics.find((t) => t.id === "quadratic-formula") as Topic;
    const q = topic.practiceQuestions[0];
    topic.practiceQuestions.push({ ...q });
    const result = validateCurriculumCatalog(catalog);
    expect(result.ok).toBe(false);
    expect(result.issues.some((i) => i.message.includes("duplicate id"))).toBe(true);
  });

  it("detects broken related topic references", () => {
    const catalog = structuredClone(service.getCatalogForTests()) as CurriculumCatalog;
    const topic = catalog.topics.find((t) => t.id === "quadratic-formula") as Topic;
    topic.relatedTopicIds = ["does-not-exist"];
    const result = validateCurriculumCatalog(catalog);
    expect(result.ok).toBe(false);
    expect(
      result.issues.some((i) => i.message.includes("unknown related topic")),
    ).toBe(true);
  });

  it("rejects topics with too few practice questions", () => {
    const catalog = structuredClone(service.getCatalogForTests()) as CurriculumCatalog;
    const topic = catalog.topics.find((t) => t.id === "discriminant") as Topic;
    topic.practiceQuestions = topic.practiceQuestions.slice(0, 1);
    const result = validateCurriculumCatalog(catalog);
    expect(result.ok).toBe(false);
    expect(
      result.issues.some((i) => i.message.includes("at least 3 practice")),
    ).toBe(true);
  });

  it("keeps question/topic relationships consistent", () => {
    for (const topic of service.getCatalogForTests().topics) {
      for (const question of topic.practiceQuestions) {
        expect(service.getTopicIdForQuestion(question.id)).toBe(topic.id);
      }
    }
  });
});

describe("answer matching", () => {
  it("normalizes unicode minus and spaces", () => {
    expect(normalizeAnswer("  X² − 5x  ")).toBe("x^2 - 5x");
  });

  it("matches accepted alternate answers", () => {
    expect(
      answersMatch("x=5, x=2", "x = 5 or x = 2", ["x=5, x=2", "5 and 2"]),
    ).toBe(true);
    expect(answersMatch("wrong", "x = 5 or x = 2", ["x=5, x=2"])).toBe(false);
  });
});

describe("content inventory smoke", () => {
  it("has populated content across all math topics", () => {
    const topics = service.getCatalogForTests().topics;
    expect(topics.length).toBe(14);
    let examples = 0;
    let questions = 0;
    for (const topic of topics) {
      expect(topic.conceptNotes.length).toBeGreaterThanOrEqual(2);
      expect(topic.examples.length).toBeGreaterThanOrEqual(2);
      expect(topic.practiceQuestions.length).toBeGreaterThanOrEqual(3);
      examples += topic.examples.length;
      questions += topic.practiceQuestions.length;
    }
    // Exact inventory snapshot for Phase 2 completion reporting.
    expect({ examples, questions }).toEqual({ examples: 31, questions: 73 });
  });
});
