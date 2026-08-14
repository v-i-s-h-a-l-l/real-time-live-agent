import { NextResponse } from "next/server";

import { readAccessUserId, unauthorized } from "@/lib/server/session";

export async function GET() {
  const userId = await readAccessUserId();
  if (!userId) {
    return unauthorized();
  }
  return NextResponse.json({ id: userId });
}
