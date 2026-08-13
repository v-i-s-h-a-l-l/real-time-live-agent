import type { Topic, TutorSessionContext } from "@/domain/curriculum/types";
import type { CurriculumCatalog } from "@/domain/curriculum/types";
import type { JsonObject } from "@/lib/voice/types";

export class CurriculumLookupError extends Error {
  readonly code: "NOT_FOUND" | "INCONSISTENT";

  constructor(code: CurriculumLookupError["code"], message: string) {
    super(message);
    this.name = "CurriculumLookupError";
    this.code = code;
  }
}

export function buildTutorSessionContext(
  catalog: CurriculumCatalog,
  topicId: string,
): TutorSessionContext {
  const topic = catalog.topics.find((t) => t.id === topicId);
  if (!topic) {
    throw new CurriculumLookupError(
      "NOT_FOUND",
      `Unknown topic: ${topicId}`,
    );
  }

  const chapter = catalog.chapters.find((c) => c.id === topic.chapterId);
  if (!chapter) {
    throw new CurriculumLookupError(
      "INCONSISTENT",
      `Topic ${topicId} references missing chapter ${topic.chapterId}`,
    );
  }

  const subject = catalog.subjects.find((s) => s.id === chapter.subjectId);
  if (!subject) {
    throw new CurriculumLookupError(
      "INCONSISTENT",
      `Chapter ${chapter.id} references missing subject ${chapter.subjectId}`,
    );
  }

  const schoolClass = catalog.classes.find((c) => c.id === subject.classId);
  if (!schoolClass) {
    throw new CurriculumLookupError(
      "INCONSISTENT",
      `Subject ${subject.id} references missing class ${subject.classId}`,
    );
  }

  return {
    classId: schoolClass.id,
    classLabel: schoolClass.label,
    subjectId: subject.id,
    subjectName: subject.name,
    chapterId: chapter.id,
    chapterTitle: chapter.title,
    topicId: topic.id,
    topicTitle: topic.title,
    topicDescription: topic.shortDescription,
    learningObjectives: [...topic.learningObjectives],
    difficulty: topic.difficulty,
  };
}

/** Compact payload for the voice WebSocket (no giant lesson text). */
export function toVoiceSessionPayload(context: TutorSessionContext): JsonObject {
  return {
    classId: context.classId,
    classLabel: context.classLabel,
    subjectId: context.subjectId,
    subjectName: context.subjectName,
    chapterId: context.chapterId,
    chapterTitle: context.chapterTitle,
    topicId: context.topicId,
    topicTitle: context.topicTitle,
    topicDescription: context.topicDescription,
    learningObjectives: context.learningObjectives,
    difficulty: context.difficulty,
  };
}

export function assertTopicBelongsToChapter(
  topic: Topic,
  chapterId: string,
): void {
  if (topic.chapterId !== chapterId) {
    throw new CurriculumLookupError(
      "INCONSISTENT",
      `Topic ${topic.id} does not belong to chapter ${chapterId}`,
    );
  }
}
