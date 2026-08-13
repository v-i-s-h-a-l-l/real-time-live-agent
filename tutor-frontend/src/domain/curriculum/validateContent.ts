import type {
  CurriculumCatalog,
  Difficulty,
  PracticeQuestion,
  QuestionStyle,
  Topic,
  WorkedExample,
} from "@/domain/curriculum/types";

const DIFFICULTIES: ReadonlySet<string> = new Set(["easy", "medium", "hard"]);
const QUESTION_STYLES: ReadonlySet<string> = new Set([
  "direct",
  "conceptual",
  "multi-step",
  "reasoning",
  "exam-style",
  "error-identification",
  "word-problem",
]);

export interface ContentValidationIssue {
  path: string;
  message: string;
}

export interface ContentValidationResult {
  ok: boolean;
  issues: ContentValidationIssue[];
}

function requireNonEmptyString(
  value: unknown,
  path: string,
  issues: ContentValidationIssue[],
): value is string {
  if (typeof value !== "string" || value.trim().length === 0) {
    issues.push({ path, message: "must be a non-empty string" });
    return false;
  }
  return true;
}

function requireStringArray(
  value: unknown,
  path: string,
  issues: ContentValidationIssue[],
  min = 0,
): value is string[] {
  if (!Array.isArray(value) || !value.every((v) => typeof v === "string")) {
    issues.push({ path, message: "must be a string array" });
    return false;
  }
  if (value.length < min) {
    issues.push({ path, message: `must contain at least ${min} item(s)` });
    return false;
  }
  return true;
}

function isDifficulty(value: unknown): value is Difficulty {
  return typeof value === "string" && DIFFICULTIES.has(value);
}

function isQuestionStyle(value: unknown): value is QuestionStyle {
  return typeof value === "string" && QUESTION_STYLES.has(value);
}

function validateExample(
  example: WorkedExample,
  path: string,
  issues: ContentValidationIssue[],
  seenIds: Set<string>,
): void {
  requireNonEmptyString(example.id, `${path}.id`, issues);
  if (seenIds.has(example.id)) {
    issues.push({ path: `${path}.id`, message: `duplicate id '${example.id}'` });
  } else if (example.id) {
    seenIds.add(example.id);
  }
  requireNonEmptyString(example.title, `${path}.title`, issues);
  requireNonEmptyString(example.question, `${path}.question`, issues);
  requireStringArray(example.steps, `${path}.steps`, issues, 1);
  requireNonEmptyString(example.answer, `${path}.answer`, issues);
  requireNonEmptyString(example.explanation, `${path}.explanation`, issues);
}

function validatePracticeQuestion(
  question: PracticeQuestion,
  path: string,
  issues: ContentValidationIssue[],
  seenIds: Set<string>,
  conceptNoteIds: Set<string>,
): void {
  requireNonEmptyString(question.id, `${path}.id`, issues);
  if (seenIds.has(question.id)) {
    issues.push({ path: `${path}.id`, message: `duplicate id '${question.id}'` });
  } else if (question.id) {
    seenIds.add(question.id);
  }
  requireNonEmptyString(question.question, `${path}.question`, issues);
  if (!isDifficulty(question.difficulty)) {
    issues.push({ path: `${path}.difficulty`, message: "invalid difficulty" });
  }
  if (!isQuestionStyle(question.style)) {
    issues.push({ path: `${path}.style`, message: "invalid question style" });
  }
  requireStringArray(question.hints, `${path}.hints`, issues, 1);
  requireNonEmptyString(question.expectedAnswer, `${path}.expectedAnswer`, issues);
  requireStringArray(question.solution, `${path}.solution`, issues, 1);
  if (question.acceptedAnswers !== undefined) {
    requireStringArray(question.acceptedAnswers, `${path}.acceptedAnswers`, issues);
  }
  if (question.conceptNoteIds) {
    for (const conceptId of question.conceptNoteIds) {
      if (!conceptNoteIds.has(conceptId)) {
        issues.push({
          path: `${path}.conceptNoteIds`,
          message: `unknown concept note '${conceptId}'`,
        });
      }
    }
  }
}

function validateTopic(
  topic: Topic,
  path: string,
  issues: ContentValidationIssue[],
  globalIds: Set<string>,
): void {
  requireNonEmptyString(topic.id, `${path}.id`, issues);
  requireNonEmptyString(topic.chapterId, `${path}.chapterId`, issues);
  requireNonEmptyString(topic.title, `${path}.title`, issues);
  requireNonEmptyString(topic.shortDescription, `${path}.shortDescription`, issues);
  requireStringArray(topic.learningObjectives, `${path}.learningObjectives`, issues, 1);
  requireStringArray(topic.prerequisites, `${path}.prerequisites`, issues);
  requireStringArray(topic.keyPoints, `${path}.keyPoints`, issues, 1);
  requireStringArray(topic.formulas, `${path}.formulas`, issues);
  requireStringArray(topic.commonMistakes, `${path}.commonMistakes`, issues, 1);
  requireStringArray(topic.hints, `${path}.hints`, issues, 1);
  requireStringArray(topic.relatedTopicIds, `${path}.relatedTopicIds`, issues);

  if (!isDifficulty(topic.difficulty)) {
    issues.push({ path: `${path}.difficulty`, message: "invalid difficulty" });
  }
  if (typeof topic.estimatedMinutes !== "number" || topic.estimatedMinutes <= 0) {
    issues.push({
      path: `${path}.estimatedMinutes`,
      message: "must be a positive number",
    });
  }

  if (!Array.isArray(topic.conceptNotes) || topic.conceptNotes.length < 1) {
    issues.push({
      path: `${path}.conceptNotes`,
      message: "must contain at least one concept note",
    });
  }

  const conceptIds = new Set<string>();
  for (const [i, note] of (topic.conceptNotes ?? []).entries()) {
    const notePath = `${path}.conceptNotes[${i}]`;
    requireNonEmptyString(note.id, `${notePath}.id`, issues);
    requireNonEmptyString(note.title, `${notePath}.title`, issues);
    requireNonEmptyString(note.body, `${notePath}.body`, issues);
    if (note.id) {
      if (conceptIds.has(note.id)) {
        issues.push({ path: `${notePath}.id`, message: `duplicate concept id '${note.id}'` });
      }
      conceptIds.add(note.id);
    }
  }

  if (!Array.isArray(topic.examples) || topic.examples.length < 1) {
    issues.push({ path: `${path}.examples`, message: "must contain at least one example" });
  }
  for (const [i, example] of (topic.examples ?? []).entries()) {
    validateExample(example, `${path}.examples[${i}]`, issues, globalIds);
  }

  if (!Array.isArray(topic.practiceQuestions) || topic.practiceQuestions.length < 3) {
    issues.push({
      path: `${path}.practiceQuestions`,
      message: "must contain at least 3 practice questions",
    });
  }
  for (const [i, question] of (topic.practiceQuestions ?? []).entries()) {
    validatePracticeQuestion(
      question,
      `${path}.practiceQuestions[${i}]`,
      issues,
      globalIds,
      conceptIds,
    );
  }
}

/**
 * Validates a full curriculum catalog for schema and referential integrity.
 * Intended for tests and build-time checks — no runtime network I/O.
 */
export function validateCurriculumCatalog(
  catalog: CurriculumCatalog,
): ContentValidationResult {
  const issues: ContentValidationIssue[] = [];
  const topicIds = new Set<string>();
  const chapterIds = new Set<string>();
  const subjectIds = new Set<string>();
  const classIds = new Set<string>();
  const globalContentIds = new Set<string>();

  for (const schoolClass of catalog.classes) {
    if (!requireNonEmptyString(schoolClass.id, `classes.${schoolClass.id}.id`, issues)) {
      continue;
    }
    if (classIds.has(schoolClass.id)) {
      issues.push({ path: `classes.${schoolClass.id}`, message: "duplicate class id" });
    }
    classIds.add(schoolClass.id);
  }

  for (const subject of catalog.subjects) {
    if (!requireNonEmptyString(subject.id, `subjects.${subject.id}.id`, issues)) continue;
    if (subjectIds.has(subject.id)) {
      issues.push({ path: `subjects.${subject.id}`, message: "duplicate subject id" });
    }
    subjectIds.add(subject.id);
    if (!classIds.has(subject.classId)) {
      issues.push({
        path: `subjects.${subject.id}.classId`,
        message: `unknown class '${subject.classId}'`,
      });
    }
  }

  for (const chapter of catalog.chapters) {
    if (!requireNonEmptyString(chapter.id, `chapters.${chapter.id}.id`, issues)) continue;
    if (chapterIds.has(chapter.id)) {
      issues.push({ path: `chapters.${chapter.id}`, message: "duplicate chapter id" });
    }
    chapterIds.add(chapter.id);
    if (!subjectIds.has(chapter.subjectId)) {
      issues.push({
        path: `chapters.${chapter.id}.subjectId`,
        message: `unknown subject '${chapter.subjectId}'`,
      });
    }
    requireStringArray(chapter.topicIds, `chapters.${chapter.id}.topicIds`, issues, 1);
  }

  for (const [index, topic] of catalog.topics.entries()) {
    const path = `topics[${index}](${topic.id ?? "?"})`;
    if (topic.id) {
      if (topicIds.has(topic.id)) {
        issues.push({ path: `${path}.id`, message: `duplicate topic id '${topic.id}'` });
      }
      topicIds.add(topic.id);
    }
    validateTopic(topic, path, issues, globalContentIds);
    if (topic.chapterId && !chapterIds.has(topic.chapterId)) {
      issues.push({
        path: `${path}.chapterId`,
        message: `unknown chapter '${topic.chapterId}'`,
      });
    }
  }

  for (const chapter of catalog.chapters) {
    for (const topicId of chapter.topicIds) {
      if (!topicIds.has(topicId)) {
        issues.push({
          path: `chapters.${chapter.id}.topicIds`,
          message: `missing topic '${topicId}'`,
        });
      }
    }
  }

  for (const topic of catalog.topics) {
    for (const relatedId of topic.relatedTopicIds) {
      if (!topicIds.has(relatedId)) {
        issues.push({
          path: `topics.${topic.id}.relatedTopicIds`,
          message: `unknown related topic '${relatedId}'`,
        });
      }
    }
  }

  for (const subject of catalog.subjects) {
    for (const chapterId of subject.chapterIds) {
      if (!chapterIds.has(chapterId)) {
        issues.push({
          path: `subjects.${subject.id}.chapterIds`,
          message: `unknown chapter '${chapterId}'`,
        });
      }
    }
  }

  return { ok: issues.length === 0, issues };
}

export function assertValidCurriculum(catalog: CurriculumCatalog): void {
  const result = validateCurriculumCatalog(catalog);
  if (!result.ok) {
    const summary = result.issues
      .slice(0, 12)
      .map((i) => `${i.path}: ${i.message}`)
      .join("; ");
    throw new Error(`Invalid curriculum content (${result.issues.length} issues): ${summary}`);
  }
}
