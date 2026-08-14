import type { PracticeQuestion, Topic } from "@/domain/curriculum/types";

/**
 * Student-visible topic: practice keys stay on the server.
 * `hintCount` is preserved so the UI can fetch hints on demand.
 */
export function toPublicTopic(topic: Topic): Topic {
  return {
    ...topic,
    practiceQuestions: topic.practiceQuestions.map(toPublicPracticeQuestion),
  };
}

export function toPublicPracticeQuestion(question: PracticeQuestion): PracticeQuestion {
  return {
    id: question.id,
    question: question.question,
    difficulty: question.difficulty,
    style: question.style,
    hints: [],
    expectedAnswer: "",
    solution: [],
    conceptNoteIds: question.conceptNoteIds,
    hintCount: question.hints.length,
  };
}

export function practiceHintCount(question: PracticeQuestion): number {
  return question.hintCount ?? question.hints.length;
}
