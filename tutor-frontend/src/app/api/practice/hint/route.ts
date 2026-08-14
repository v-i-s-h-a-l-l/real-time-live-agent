import { NextResponse } from "next/server";

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
  const index = Number((body as { index?: unknown }).index ?? 0);
  if (!questionId || questionId.length > 80) {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  if (!Number.isInteger(index) || index < 0 || index > 32) {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  const hint = curriculumService.getHint(questionId, index);
  if (hint == null) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return NextResponse.json({ hint, index });
}
