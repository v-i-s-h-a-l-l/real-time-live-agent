/**
 * Practice answer evaluation for the lesson UI.
 *
 * Port of `server/tutor/practice.py`. The tutor scores spoken and typed answers on
 * the backend; this runs the same rules locally so the practice card can react
 * instantly and identically. `shared/practice-answer-cases.json` is asserted by both
 * test suites, so the two implementations cannot drift.
 */

export type AnswerEvaluation =
  | "correct"
  | "partially_correct"
  | "incorrect"
  | "needs_hint"
  | "hint_request"
  | "conceptual_question"
  | "ambiguous";

export type MasteryLevel =
  | "not_started"
  | "learning"
  | "developing"
  | "strong"
  | "mastered";

export interface EvaluationResult {
  evaluation: AnswerEvaluation;
  reason: string;
  missingValues: number[];
}

const HINT_REQUEST =
  /\b(hint|clue|nudge|point me|give me (?:a |some )?help|help me (?:out|a bit)|thoda hint)\b/i;

const DONT_KNOW =
  /(\bi (?:really )?(?:don'?t|do not|dont) know\b|\bno (?:idea|clue)\b|\bnot sure(?: at all)?\b|\bcan'?t (?:figure|work) (?:it|this) out\b|\bi'?m stuck\b|\bi am stuck\b|\bpata nahi\b)/i;

const CONCEPTUAL =
  /(\bwhy (?:do|does|is|are|would|should|can'?t)\b|\bhow (?:come|does that|do we|does this) \b|\bwhat (?:does|do) (?:that|this|it) mean\b|\bwhere (?:does|did) (?:that|this|it) come from\b)/i;

const LEAD_IN =
  /^\s*(?:i (?:think|guess|believe|got|reckon)(?: (?:it'?s|its|that|the answer is))?|maybe|probably|i'?d say|umm+|uhh+|well|so|okay|ok|hmm+|the answer (?:is|would be|should be)|answer(?: is|:)|it(?:'s| is)|that(?:'s| is)|they(?:'re| are)|the (?:zeros?|roots?|values?) (?:are|is))\b[\s,:-]*/i;

const TRAILING_HEDGE =
  /[\s,;.]*\b(?:but )?(?:i'?m|i am) not (?:really )?sure(?: about (?:it|that|this))?\s*[.!?]*\s*$/i;

const NUMBER = /-?\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)?/g;
const FACTOR_PAIR = /\(\s*[a-z]\s*([+-])\s*(\d+(?:\.\d+)?)\s*\)/gi;
const EXPONENT = /(?:\^|\*\*)\s*-?\d+/g;
const FINAL_SEGMENT =
  /\b(?:so|then|therefore|hence|thus|which means|answer is|answer:)\b/gi;

const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
  "for", "from", "get", "gets", "has", "have", "in", "into", "is", "it",
  "its", "of", "on", "or", "so", "than", "that", "the", "then", "there",
  "these", "they", "this", "to", "was", "we", "were", "will", "with",
]);

export function normalizeQuotes(value: string): string {
  return (value ?? "").replace(/[\u2018\u2019]/g, "'");
}

export function normalizeAnswer(value: string): string {
  return normalizeQuotes(value)
    .trim()
    .toLowerCase()
    .replace(/[\u2212\u2013\u2014]/g, "-")
    .replace(/\u00d7/g, "*")
    .replace(/\u00f7/g, "/")
    .replace(/\u00b2/g, "^2")
    .replace(/\u00b3/g, "^3")
    .replace(/\s+/g, " ")
    .replace(/[.,;:!?]+$/g, "")
    .trim();
}

export function stripConversationalPadding(value: string): string {
  let text = normalizeQuotes(value).replace(TRAILING_HEDGE, "");
  let previous: string | null = null;
  while (previous !== text) {
    previous = text;
    text = text.replace(LEAD_IN, "");
  }
  return text.replace(/^[\s,:-]+|[\s,:-]+$/g, "");
}

function parseNumber(token: string): number | null {
  const raw = token.replace(/\s/g, "");
  if (raw.includes("/")) {
    const [numerator, denominator] = raw.split("/");
    const denom = Number(denominator);
    if (!Number.isFinite(denom) || denom === 0) return null;
    const num = Number(numerator);
    return Number.isFinite(num) ? num / denom : null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function quantize(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

export function extractValues(text: string): Set<number> {
  const cleaned = (text ?? "")
    .replace(/[\u2212\u2013\u2014]/g, "-")
    .replace(/\u00b2/g, "^2")
    .replace(/\u00b3/g, "^3")
    // Exponents are notation, not answer values: x^2 must not contribute a "2".
    .replace(EXPONENT, " ");

  const values = new Set<number>();
  for (const match of cleaned.matchAll(FACTOR_PAIR)) {
    const parsed = parseNumber(match[2]);
    if (parsed !== null) values.add(quantize(match[1] === "+" ? -parsed : parsed));
  }
  for (const match of cleaned.matchAll(NUMBER)) {
    const parsed = parseNumber(match[0]);
    if (parsed !== null) values.add(quantize(parsed));
  }
  return values;
}

function finalSegment(text: string): string {
  const matches = [...(text ?? "").matchAll(FINAL_SEGMENT)];
  if (matches.length === 0) return text ?? "";
  const last = matches[matches.length - 1];
  const tail = (text ?? "").slice((last.index ?? 0) + last[0].length).trim();
  return tail || (text ?? "");
}

function contentTokens(text: string): Set<string> {
  const tokens = normalizeAnswer(text).match(/[a-z]+|\d+(?:\.\d+)?/g) ?? [];
  return new Set(tokens.filter((token) => !STOP_WORDS.has(token)));
}

function tokenOverlap(student: string, candidate: string): number {
  const studentTokens = contentTokens(student);
  const candidateTokens = contentTokens(candidate);
  if (candidateTokens.size === 0 || studentTokens.size === 0) return 0;
  let shared = 0;
  for (const token of candidateTokens) if (studentTokens.has(token)) shared += 1;
  return shared / candidateTokens.size;
}

function isSubsetOf(a: Set<number>, b: Set<number>): boolean {
  for (const value of a) if (!b.has(value)) return false;
  return true;
}

export function classifyPracticeResponse(
  utterance: string,
): AnswerEvaluation | null {
  const raw = normalizeQuotes(utterance).trim();
  if (!raw) return "ambiguous";
  // "…, but I'm not sure." is a hedge on an answer; "I'm not sure." on its own is not.
  const text = raw.replace(TRAILING_HEDGE, "").trim() || raw;
  if (HINT_REQUEST.test(text)) return "hint_request";
  if (DONT_KNOW.test(text)) return "needs_hint";
  if (CONCEPTUAL.test(text)) return "conceptual_question";
  return null;
}

export function evaluateAnswer(
  utterance: string,
  expectedAnswer: string | null | undefined,
  acceptedAnswers: readonly string[] = [],
): EvaluationResult {
  const nonAnswer = classifyPracticeResponse(utterance);
  if (nonAnswer) return { evaluation: nonAnswer, reason: "", missingValues: [] };

  const studentRaw = stripConversationalPadding(utterance);
  const studentNorm = normalizeAnswer(studentRaw);
  if (!studentNorm) {
    return { evaluation: "ambiguous", reason: "empty response", missingValues: [] };
  }

  const candidates = [expectedAnswer ?? "", ...acceptedAnswers].filter(
    (candidate) => candidate.trim().length > 0,
  );
  if (candidates.length === 0) {
    return {
      evaluation: "ambiguous",
      reason: "no expected answer available",
      missingValues: [],
    };
  }

  for (const candidate of candidates) {
    if (studentNorm === normalizeAnswer(stripConversationalPadding(candidate))) {
      return { evaluation: "correct", reason: "exact match", missingValues: [] };
    }
  }

  const studentValues = extractValues(studentRaw);
  const finalValues = extractValues(finalSegment(studentRaw));

  let partial: EvaluationResult | null = null;
  for (const candidate of candidates) {
    const expectedValues = extractValues(candidate);
    if (expectedValues.size === 0) continue;

    for (const values of [finalValues, studentValues]) {
      if (values.size === 0) continue;
      if (
        values.size === expectedValues.size &&
        isSubsetOf(values, expectedValues)
      ) {
        return { evaluation: "correct", reason: "numeric match", missingValues: [] };
      }
      if (
        isSubsetOf(expectedValues, values) &&
        values.size <= expectedValues.size + 3
      ) {
        // They showed working and landed on every required value.
        return {
          evaluation: "correct",
          reason: "answer stated with working",
          missingValues: [],
        };
      }
      if (isSubsetOf(values, expectedValues) && values.size < expectedValues.size) {
        partial = {
          evaluation: "partially_correct",
          reason: "part of the answer is missing",
          missingValues: [...expectedValues]
            .filter((value) => !values.has(value))
            .sort((a, b) => a - b),
        };
      }
    }
  }

  if (partial) return partial;

  for (const candidate of candidates) {
    if (extractValues(candidate).size > 0) continue;
    const overlap = tokenOverlap(studentRaw, candidate);
    if (overlap >= 0.7) {
      return { evaluation: "correct", reason: "wording match", missingValues: [] };
    }
    if (overlap >= 0.4) {
      return {
        evaluation: "partially_correct",
        reason: "partial wording match",
        missingValues: [],
      };
    }
  }

  if (studentValues.size === 0 && studentNorm.split(" ").length <= 2) {
    return {
      evaluation: "ambiguous",
      reason: "not an interpretable attempt",
      missingValues: [],
    };
  }

  return {
    evaluation: "incorrect",
    reason: "does not match the expected answer",
    missingValues: [],
  };
}
