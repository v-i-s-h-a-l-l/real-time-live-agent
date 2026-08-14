import { NextResponse } from "next/server";

import {
  AuthRequiredError,
  csrfAllowed,
  requireUserId,
  unauthorized,
} from "@/lib/server/session";
import { mintVoiceTicket, sessionSecret } from "@/lib/server/signing";

export async function POST(request: Request) {
  if (!csrfAllowed(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  try {
    const userId = await requireUserId();
    const secret = sessionSecret();
    if (!secret) {
      if (process.env.NODE_ENV === "production") {
        return NextResponse.json({ error: "not_ready" }, { status: 503 });
      }
      return NextResponse.json({ token: null });
    }
    return NextResponse.json({ token: mintVoiceTicket(secret, userId) });
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return unauthorized();
    }
    throw error;
  }
}
