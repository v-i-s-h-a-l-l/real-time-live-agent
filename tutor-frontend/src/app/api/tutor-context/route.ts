import { NextResponse } from "next/server";

import { curriculumService } from "@/services/curriculum/CurriculumService";
import { sessionSecret, signTutorPayload } from "@/lib/server/signing";
import {
  AuthRequiredError,
  csrfAllowed,
  requireUserId,
  unauthorized,
} from "@/lib/server/session";

export async function POST(request: Request) {
  if (!csrfAllowed(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  try {
    await requireUserId();
  } catch (error) {
    if (error instanceof AuthRequiredError) return unauthorized();
    throw error;
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  const topicId = String((body as { topicId?: unknown }).topicId ?? "").trim();
  const questionId = String(
    (body as { questionId?: unknown }).questionId ?? "",
  ).trim();
  const phase = String((body as { phase?: unknown }).phase ?? "learning").trim() || "learning";
  if (!topicId || topicId.length > 80 || questionId.length > 80) {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }

  const topic = curriculumService.getTopic(topicId);
  if (!topic) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const payload: Record<string, unknown> = {
    topicId: topic.id,
    phase,
    prerequisites: [...topic.prerequisites],
    commonMistakes: [...topic.commonMistakes],
    topicHints: [...topic.hints],
  };

  if (phase === "practice" && questionId) {
    const question = curriculumService.getQuestion(questionId);
    const belongs = curriculumService.getTopicIdForQuestion(questionId) === topic.id;
    if (!question || !belongs) {
      return NextResponse.json({ error: "not_found" }, { status: 404 });
    }
    payload.questionId = question.id;
    payload.hints = [...question.hints];
    payload.expectedAnswer = question.expectedAnswer;
    payload.acceptedAnswers = [...(question.acceptedAnswers ?? [])];
    payload.solution = [...question.solution];
  }

  const secret = sessionSecret();
  if (!secret) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json({ error: "not_ready" }, { status: 503 });
    }
    return NextResponse.json({ context: payload });
  }
  return NextResponse.json({ context: signTutorPayload(payload, secret) });
}
