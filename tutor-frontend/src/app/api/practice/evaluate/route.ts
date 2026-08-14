import { NextResponse } from "next/server";

import { evaluateAnswer } from "@/domain/practice/evaluation";
import { curriculumService } from "@/services/curriculum/CurriculumService";
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
  const questionId = String(
    (body as { questionId?: unknown }).questionId ?? "",
  ).trim();
  const answer = String((body as { answer?: unknown }).answer ?? "");
  if (!questionId || questionId.length > 80 || answer.length > 2000) {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  const question = curriculumService.getQuestion(questionId);
  if (!question) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  const result = evaluateAnswer(
    answer,
    question.expectedAnswer,
    question.acceptedAnswers ?? [],
  );
  return NextResponse.json({ evaluation: result.evaluation });
}
