/**
 * Thin compatibility layer over the shared practice evaluator.
 * There is one evaluation implementation per side of the wire, not one per input mode.
 */

import { evaluateAnswer } from "@/domain/practice/evaluation";

export { normalizeAnswer } from "@/domain/practice/evaluation";

export function answersMatch(
  studentAnswer: string,
  expectedAnswer: string,
  acceptedAnswers: string[] = [],
): boolean {
  return (
    evaluateAnswer(studentAnswer, expectedAnswer, acceptedAnswers).evaluation ===
    "correct"
  );
}
