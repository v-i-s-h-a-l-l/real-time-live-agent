import type {
  Difficulty,
  PracticeQuestion,
  Topic,
  TutorSessionContext,
} from "@/domain/curriculum/types";
import { selectNextQuestion } from "@/domain/practice/adaptive";
import type { JsonObject } from "@/lib/voice/types";

export type LessonPhase = "learning" | "practice" | "completed";

export type LessonUnitType =
  | "concept"
  | "formula"
  | "example"
  | "mistake"
  | "overview";

/** One sequential on-screen learning unit (derived from curriculum content). */
export interface LessonUnit {
  id: string;
  title: string;
  type: LessonUnitType;
  body: string;
  keyPoints: string[];
  formulas: string[];
  /** Present for worked-example units. */
  steps?: string[];
  answer?: string;
}

export interface LessonState {
  topicId: string;
  phase: LessonPhase;
  currentSectionIndex: number;
  currentQuestionIndex: number | null;
  /** Practice questions already shown, oldest first. Drives adaptive selection. */
  visitedQuestionIds?: string[];
}

export interface LessonAdvanceOptions {
  /**
   * Difficulty the tutor recommends for the next question, from the live practice
   * state. Omitted (no voice session yet) keeps the plain curriculum order.
   */
  targetDifficulty?: Difficulty;
}

export interface LessonSnapshot {
  state: LessonState;
  units: LessonUnit[];
  questions: PracticeQuestion[];
  currentUnit: LessonUnit | null;
  currentQuestion: PracticeQuestion | null;
  sectionProgress: { current: number; total: number } | null;
  questionProgress: { current: number; total: number } | null;
  canGoPrevious: boolean;
  canGoNext: boolean;
  nextLabel: string;
}

/**
 * Student-facing active context — never includes hidden solutions.
 * Sent to the voice engine as `{ type: "learning_context", context }`.
 */
export interface StudentVisibleLearningContext {
  classId: string;
  classLabel: string;
  subjectId: string;
  subjectName: string;
  chapterId: string;
  chapterTitle: string;
  topicId: string;
  topicTitle: string;
  phase: LessonPhase;
  sectionId?: string;
  sectionTitle?: string;
  sectionType?: LessonUnitType;
  visibleContent?: string;
  keyPoints?: string[];
  formulas?: string[];
  questionId?: string;
  question?: string;
  difficulty?: Difficulty;
  hintCount?: number;
  progressLabel: string;
}

/**
 * Tutor-only enrichment for the voice Tutor Engine (hints / expected answer / solution).
 * Must not be sent as student-visible learning_context.
 */
export interface TutorOnlyLearningContext {
  topicId: string;
  phase: LessonPhase;
  prerequisites: string[];
  commonMistakes: string[];
  topicHints: string[];
  questionId?: string;
  hints?: string[];
  expectedAnswer?: string;
  acceptedAnswers?: string[];
  solution?: string[];
}

/** Build sequential lesson units from existing topic content (no duplicated storage). */
export function buildLessonUnits(topic: Topic): LessonUnit[] {
  const units: LessonUnit[] = [];

  units.push({
    id: `${topic.id}__overview`,
    title: `About ${topic.title}`,
    type: "overview",
    body: topic.shortDescription,
    keyPoints: topic.learningObjectives.slice(0, 4),
    formulas: [],
  });

  for (const note of topic.conceptNotes) {
    units.push({
      id: `${topic.id}__concept__${note.id}`,
      title: note.title,
      type: "concept",
      body: note.body,
      keyPoints: [],
      formulas: [],
    });
  }

  if (topic.formulas.length > 0) {
    units.push({
      id: `${topic.id}__formulas`,
      title: "Key formulas",
      type: "formula",
      body: "Keep these formulas in mind for this topic. You can ask the tutor to walk through any of them.",
      keyPoints: topic.keyPoints.slice(0, 3),
      formulas: [...topic.formulas],
    });
  }

  for (const example of topic.examples) {
    units.push({
      id: `${topic.id}__example__${example.id}`,
      title: example.title,
      type: "example",
      body: example.question,
      keyPoints: example.explanation ? [example.explanation] : [],
      formulas: [],
      steps: [...example.steps],
      answer: example.answer,
    });
  }

  for (const [index, mistake] of topic.commonMistakes.entries()) {
    units.push({
      id: `${topic.id}__mistake__${index + 1}`,
      title: "Common mistake",
      type: "mistake",
      body: mistake,
      keyPoints: topic.hints.slice(0, 2),
      formulas: [],
    });
  }

  return units;
}

export function createInitialLessonState(topicId: string): LessonState {
  return {
    topicId,
    phase: "learning",
    currentSectionIndex: 0,
    currentQuestionIndex: null,
    visitedQuestionIds: [],
  };
}

export function getLessonSnapshot(
  topic: Topic,
  state: LessonState,
): LessonSnapshot {
  if (state.topicId !== topic.id) {
    throw new Error(
      `Lesson state topic ${state.topicId} does not match topic ${topic.id}`,
    );
  }

  const units = buildLessonUnits(topic);
  const questions = topic.practiceQuestions;
  const totalSections = units.length;
  const totalQuestions = questions.length;

  if (state.phase === "learning") {
    const index = clamp(state.currentSectionIndex, 0, Math.max(totalSections - 1, 0));
    const currentUnit = units[index] ?? null;
    const isLast = index >= totalSections - 1;
    return {
      state: { ...state, currentSectionIndex: index, currentQuestionIndex: null },
      units,
      questions,
      currentUnit,
      currentQuestion: null,
      sectionProgress: { current: index + 1, total: totalSections },
      questionProgress: null,
      canGoPrevious: index > 0,
      canGoNext: totalSections > 0,
      nextLabel: isLast ? (totalQuestions > 0 ? "Start practice" : "Finish") : "Next",
    };
  }

  if (state.phase === "practice") {
    const index = clamp(
      state.currentQuestionIndex ?? 0,
      0,
      Math.max(totalQuestions - 1, 0),
    );
    const currentQuestion = questions[index] ?? null;
    const isLast = index >= totalQuestions - 1;
    return {
      state: {
        ...state,
        currentSectionIndex: Math.max(totalSections - 1, 0),
        currentQuestionIndex: index,
      },
      units,
      questions,
      currentUnit: null,
      currentQuestion,
      sectionProgress: null,
      questionProgress: { current: index + 1, total: totalQuestions },
      canGoPrevious: true,
      canGoNext: totalQuestions > 0,
      nextLabel: isLast ? "Finish lesson" : "Next question",
    };
  }

  return {
    state,
    units,
    questions,
    currentUnit: null,
    currentQuestion: null,
    sectionProgress: null,
    questionProgress: null,
    canGoPrevious: totalQuestions > 0 || units.length > 0,
    canGoNext: false,
    nextLabel: "Finished",
  };
}

function withVisited(state: LessonState, questionId: string | undefined): string[] {
  const visited = state.visitedQuestionIds ?? [];
  if (!questionId || visited.includes(questionId)) return visited;
  return [...visited, questionId];
}

export function goToNextLessonState(
  topic: Topic,
  state: LessonState,
  options: LessonAdvanceOptions = {},
): LessonState {
  const snapshot = getLessonSnapshot(topic, state);

  if (state.phase === "learning") {
    const index = snapshot.state.currentSectionIndex;
    const last = snapshot.units.length - 1;
    if (index < last) {
      return {
        ...state,
        phase: "learning",
        currentSectionIndex: index + 1,
        currentQuestionIndex: null,
      };
    }
    if (snapshot.questions.length > 0) {
      return {
        ...state,
        phase: "practice",
        currentSectionIndex: last,
        currentQuestionIndex: 0,
      };
    }
    return {
      ...state,
      phase: "completed",
      currentSectionIndex: Math.max(last, 0),
      currentQuestionIndex: null,
    };
  }

  if (state.phase === "practice") {
    const index = snapshot.state.currentQuestionIndex ?? 0;
    const questions = snapshot.questions;
    const visitedQuestionIds = withVisited(state, questions[index]?.id);

    if (options.targetDifficulty) {
      const next = selectNextQuestion({
        questions,
        visitedQuestionIds,
        targetDifficulty: options.targetDifficulty,
      });
      if (next) {
        return {
          ...state,
          phase: "practice",
          currentQuestionIndex: questions.indexOf(next),
          visitedQuestionIds,
        };
      }
      return {
        ...state,
        phase: "completed",
        currentQuestionIndex: Math.max(index, 0),
        visitedQuestionIds,
      };
    }

    const last = questions.length - 1;
    if (index < last) {
      return {
        ...state,
        phase: "practice",
        currentQuestionIndex: index + 1,
        visitedQuestionIds,
      };
    }
    return {
      ...state,
      phase: "completed",
      currentQuestionIndex: Math.max(last, 0),
      visitedQuestionIds,
    };
  }

  return state;
}

export function goToPreviousLessonState(
  topic: Topic,
  state: LessonState,
): LessonState {
  const snapshot = getLessonSnapshot(topic, state);

  if (state.phase === "learning") {
    const index = snapshot.state.currentSectionIndex;
    if (index <= 0) return snapshot.state;
    return {
      ...state,
      phase: "learning",
      currentSectionIndex: index - 1,
      currentQuestionIndex: null,
    };
  }

  if (state.phase === "practice") {
    const index = snapshot.state.currentQuestionIndex ?? 0;
    const visited = state.visitedQuestionIds ?? [];
    const previousId = visited[visited.length - 1];
    const previousIndex = previousId
      ? snapshot.questions.findIndex((question) => question.id === previousId)
      : -1;
    if (previousIndex >= 0) {
      // Step back along the path actually taken, which adaptive order may reorder.
      return {
        ...state,
        phase: "practice",
        currentQuestionIndex: previousIndex,
        visitedQuestionIds: visited.slice(0, -1),
      };
    }
    if (index > 0) {
      return {
        ...state,
        phase: "practice",
        currentQuestionIndex: index - 1,
      };
    }
    const lastSection = Math.max(snapshot.units.length - 1, 0);
    return {
      ...state,
      phase: "learning",
      currentSectionIndex: lastSection,
      currentQuestionIndex: null,
    };
  }

  if (state.phase === "completed") {
    if (snapshot.questions.length > 0) {
      const visited = state.visitedQuestionIds ?? [];
      const lastId = visited[visited.length - 1];
      const lastIndex = lastId
        ? snapshot.questions.findIndex((question) => question.id === lastId)
        : -1;
      return {
        ...state,
        phase: "practice",
        currentQuestionIndex:
          lastIndex >= 0 ? lastIndex : snapshot.questions.length - 1,
        visitedQuestionIds: lastIndex >= 0 ? visited.slice(0, -1) : visited,
      };
    }
    return {
      ...state,
      phase: "learning",
      currentSectionIndex: Math.max(snapshot.units.length - 1, 0),
      currentQuestionIndex: null,
    };
  }

  return state;
}

export function buildStudentVisibleLearningContext(params: {
  session: TutorSessionContext;
  topic: Topic;
  snapshot: LessonSnapshot;
}): StudentVisibleLearningContext {
  const { session, snapshot } = params;
  const base = {
    classId: session.classId,
    classLabel: session.classLabel,
    subjectId: session.subjectId,
    subjectName: session.subjectName,
    chapterId: session.chapterId,
    chapterTitle: session.chapterTitle,
    topicId: session.topicId,
    topicTitle: session.topicTitle,
    phase: snapshot.state.phase,
  };

  if (snapshot.state.phase === "learning" && snapshot.currentUnit) {
    const unit = snapshot.currentUnit;
    return {
      ...base,
      sectionId: unit.id,
      sectionTitle: unit.title,
      sectionType: unit.type,
      visibleContent: unit.body,
      keyPoints: unit.keyPoints,
      formulas: unit.formulas,
      progressLabel: `Lesson ${snapshot.sectionProgress?.current ?? 0} / ${snapshot.sectionProgress?.total ?? 0}`,
    };
  }

  if (snapshot.state.phase === "practice" && snapshot.currentQuestion) {
    const question = snapshot.currentQuestion;
    return {
      ...base,
      questionId: question.id,
      question: question.question,
      difficulty: question.difficulty,
      hintCount: question.hints.length,
      progressLabel: `Question ${snapshot.questionProgress?.current ?? 0} of ${snapshot.questionProgress?.total ?? 0}`,
    };
  }

  return {
    ...base,
    progressLabel: "Lesson complete",
  };
}

export function buildTutorOnlyLearningContext(params: {
  topic: Topic;
  snapshot: LessonSnapshot;
}): TutorOnlyLearningContext {
  const { topic, snapshot } = params;
  const base: TutorOnlyLearningContext = {
    topicId: topic.id,
    phase: snapshot.state.phase,
    prerequisites: [...topic.prerequisites],
    commonMistakes: [...topic.commonMistakes],
    topicHints: [...topic.hints],
  };

  if (snapshot.state.phase === "practice" && snapshot.currentQuestion) {
    const q = snapshot.currentQuestion;
    return {
      ...base,
      questionId: q.id,
      hints: [...q.hints],
      expectedAnswer: q.expectedAnswer,
      acceptedAnswers: [...(q.acceptedAnswers ?? [])],
      solution: [...q.solution],
    };
  }

  return base;
}

export function toLearningContextPayload(
  context: StudentVisibleLearningContext,
): JsonObject {
  return { ...context };
}

export function toTutorContextPayload(
  context: TutorOnlyLearningContext,
): JsonObject {
  return { ...context };
}

export function learningContextFingerprint(
  context: StudentVisibleLearningContext,
): string {
  return [
    context.topicId,
    context.phase,
    context.sectionId ?? "",
    context.questionId ?? "",
    context.progressLabel,
  ].join("|");
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}
