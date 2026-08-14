import { CLASS10_CURRICULUM_CATALOG } from "@/content/curriculum/class10/mathematics/catalog";
import {
  assertTopicBelongsToChapter,
  buildTutorSessionContext,
  CurriculumLookupError,
} from "@/domain/curriculum/sessionContext";
import type {
  Chapter,
  CurriculumCatalog,
  PracticeQuestion,
  SchoolClass,
  Subject,
  Topic,
  TopicContent,
  TutorSessionContext,
  WorkedExample,
} from "@/domain/curriculum/types";
import {
  assertValidCurriculum,
  validateCurriculumCatalog,
} from "@/domain/curriculum/validateContent";

/**
 * Read-only curriculum + learning-content API.
 * UI and future Tutor Engine depend on this — not on content files directly.
 */
export class CurriculumService {
  private readonly questionIndex: Map<string, { topicId: string; question: PracticeQuestion }>;

  constructor(private readonly catalog: CurriculumCatalog = CLASS10_CURRICULUM_CATALOG) {
    this.questionIndex = new Map();
    for (const topic of catalog.topics) {
      for (const question of topic.practiceQuestions) {
        this.questionIndex.set(question.id, { topicId: topic.id, question });
      }
    }
  }

  /** @internal used by unit tests */
  getCatalogForTests(): CurriculumCatalog {
    return this.catalog;
  }

  getClasses(): SchoolClass[] {
    return [...this.catalog.classes];
  }

  getClass(classId: string): SchoolClass | null {
    return this.catalog.classes.find((c) => c.id === classId) ?? null;
  }

  getSubjects(classId?: string): Subject[] {
    if (!classId) return [...this.catalog.subjects];
    return this.catalog.subjects.filter((s) => s.classId === classId);
  }

  getSubject(subjectId: string): Subject | null {
    return this.catalog.subjects.find((s) => s.id === subjectId) ?? null;
  }

  getChapters(subjectId: string): Chapter[] {
    return this.catalog.chapters
      .filter((c) => c.subjectId === subjectId)
      .slice()
      .sort((a, b) => a.order - b.order);
  }

  getChapter(chapterId: string): Chapter | null {
    return this.catalog.chapters.find((c) => c.id === chapterId) ?? null;
  }

  getTopics(chapterId: string): Topic[] {
    const chapter = this.getChapter(chapterId);
    if (!chapter) return [];

    const byId = new Map(this.catalog.topics.map((t) => [t.id, t]));
    const topics: Topic[] = [];
    for (const topicId of chapter.topicIds) {
      const topic = byId.get(topicId);
      if (!topic) {
        throw new CurriculumLookupError(
          "INCONSISTENT",
          `Chapter ${chapterId} lists missing topic ${topicId}`,
        );
      }
      assertTopicBelongsToChapter(topic, chapterId);
      topics.push(topic);
    }
    return topics;
  }

  getTopic(topicId: string): Topic | null {
    return this.catalog.topics.find((t) => t.id === topicId) ?? null;
  }

  getRelatedTopics(topicId: string): Topic[] {
    const topic = this.getTopic(topicId);
    if (!topic) return [];
    return topic.relatedTopicIds
      .map((id) => this.getTopic(id))
      .filter((t): t is Topic => t !== null);
  }

  /** Full structured learning material for a topic. */
  getTopicContent(topicId: string): TopicContent | null {
    const topic = this.getTopic(topicId);
    if (!topic) return null;
    return {
      topic,
      conceptNotes: [...topic.conceptNotes],
      keyPoints: [...topic.keyPoints],
      formulas: [...topic.formulas],
      examples: [...topic.examples],
      commonMistakes: [...topic.commonMistakes],
      hints: [...topic.hints],
      practiceQuestions: [...topic.practiceQuestions],
    };
  }

  getExamples(topicId: string): WorkedExample[] {
    return this.getTopic(topicId)?.examples.slice() ?? [];
  }

  getPracticeQuestions(topicId: string): PracticeQuestion[] {
    return this.getTopic(topicId)?.practiceQuestions.slice() ?? [];
  }

  getQuestion(questionId: string): PracticeQuestion | null {
    return this.questionIndex.get(questionId)?.question ?? null;
  }

  getHint(questionId: string, hintIndex: number): string | null {
    const question = this.getQuestion(questionId);
    if (!question) return null;
    if (hintIndex < 0 || hintIndex >= question.hints.length) return null;
    return question.hints[hintIndex] ?? null;
  }

  getSolution(questionId: string): string[] | null {
    const question = this.getQuestion(questionId);
    if (!question) return null;
    return [...question.solution];
  }

  getTopicIdForQuestion(questionId: string): string | null {
    return this.questionIndex.get(questionId)?.topicId ?? null;
  }

  createSessionContext(topicId: string): TutorSessionContext {
    return buildTutorSessionContext(this.catalog, topicId);
  }

  tryCreateSessionContext(topicId: string): TutorSessionContext | null {
    try {
      return this.createSessionContext(topicId);
    } catch (err) {
      if (err instanceof CurriculumLookupError && err.code === "NOT_FOUND") {
        return null;
      }
      throw err;
    }
  }

  /** Hierarchy checks (legacy helper). Prefer validateContent(). */
  validateIntegrity(): string[] {
    return validateCurriculumCatalog(this.catalog).issues.map(
      (issue) => `${issue.path}: ${issue.message}`,
    );
  }

  validateContent() {
    return validateCurriculumCatalog(this.catalog);
  }

  assertContentValid(): void {
    assertValidCurriculum(this.catalog);
  }
}

/** App-wide singleton for the static Class 10 catalog. */
export const curriculumService = new CurriculumService();

/** Fail the process if the catalog is invalid. */
const _curriculumCheck = curriculumService.validateContent();
if (!_curriculumCheck.ok) {
  if (process.env.NODE_ENV === "production") {
    curriculumService.assertContentValid();
  } else {
    console.error("[curriculum] validation failed:", _curriculumCheck.issues.slice(0, 20));
  }
}
