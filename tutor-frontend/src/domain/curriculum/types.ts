/**
 * Subject-agnostic curriculum content models.
 * Suitable for Mathematics, English, Sciences, and other classes.
 */

export type Difficulty = "easy" | "medium" | "hard";

export type QuestionStyle =
  | "direct"
  | "conceptual"
  | "multi-step"
  | "reasoning"
  | "exam-style"
  | "error-identification"
  | "word-problem";

/** One teachable unit within a topic (voice-tutor friendly chunks). */
export interface ConceptNote {
  id: string;
  title: string;
  body: string;
}

export interface WorkedExample {
  id: string;
  title: string;
  question: string;
  steps: string[];
  answer: string;
  explanation: string;
  commonMistake?: string;
}

export interface PracticeQuestion {
  id: string;
  question: string;
  difficulty: Difficulty;
  style: QuestionStyle;
  hints: string[];
  expectedAnswer: string;
  /** Optional alternate answers accepted by the practice UI matcher. */
  acceptedAnswers?: string[];
  /** Step-by-step solution — for tutor/engine use; hidden until revealed in UI. */
  solution: string[];
  /** When secrets are stripped for the client, the original hint list length. */
  hintCount?: number;
  /** Optional links to concept note ids within the same topic. */
  conceptNoteIds?: string[];
}

export interface Topic {
  id: string;
  chapterId: string;
  title: string;
  shortDescription: string;
  learningObjectives: string[];
  prerequisites: string[];
  conceptNotes: ConceptNote[];
  keyPoints: string[];
  formulas: string[];
  examples: WorkedExample[];
  commonMistakes: string[];
  /** Topic-level study hints (not question-specific). */
  hints: string[];
  practiceQuestions: PracticeQuestion[];
  difficulty: Difficulty;
  relatedTopicIds: string[];
  estimatedMinutes: number;
}

export interface Chapter {
  id: string;
  subjectId: string;
  title: string;
  description: string;
  order: number;
  topicIds: string[];
}

export interface Subject {
  id: string;
  classId: string;
  name: string;
  description: string;
  available: boolean;
  chapterIds: string[];
}

export interface SchoolClass {
  id: string;
  label: string;
  grade: number;
  subjectIds: string[];
}

/** Serializable curriculum payload sent to the domain-agnostic voice engine. */
export interface TutorSessionContext {
  classId: string;
  classLabel: string;
  subjectId: string;
  subjectName: string;
  chapterId: string;
  chapterTitle: string;
  topicId: string;
  topicTitle: string;
  topicDescription: string;
  learningObjectives: string[];
  difficulty: Difficulty;
}

export interface CurriculumCatalog {
  classes: SchoolClass[];
  subjects: Subject[];
  chapters: Chapter[];
  topics: Topic[];
}

/** Public learning material for a topic (solutions omitted for LMS display helpers). */
export interface TopicContent {
  topic: Topic;
  conceptNotes: ConceptNote[];
  keyPoints: string[];
  formulas: string[];
  examples: WorkedExample[];
  commonMistakes: string[];
  hints: string[];
  practiceQuestions: PracticeQuestion[];
}
