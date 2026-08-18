/**
 * HMAC helpers for voice session tokens and tutor-only payloads.
 * Server-only — never import from a client component.
 */

import { createHmac } from "crypto";

export function stableStringify(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "null";
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(",")}}`;
  }
  return "null";
}

export function hmacHex(body: string, secret: string): string {
  return createHmac("sha256", secret).update(body, "utf8").digest("hex");
}

export function mintSessionToken(secret: string, ttlSecs = 2 * 60 * 60): string {
  const exp = Math.floor(Date.now() / 1000) + ttlSecs;
  const body = String(exp);
  return `${body}.${hmacHex(body, secret)}`;
}

/** Short-lived single-use voice ticket: v1.exp.jti.sub.sig */
export function mintVoiceTicket(
  secret: string,
  userId: string,
  ttlSecs = 90,
): string {
  if (userId.includes(".")) {
    throw new Error("invalid_user");
  }
  const exp = Math.floor(Date.now() / 1000) + ttlSecs;
  const jti = crypto.randomUUID().replaceAll("-", "");
  const body = `v1.${exp}.${jti}.${userId}`;
  return `${body}.${hmacHex(body, secret)}`;
}

export function signTutorPayload(
  payload: Record<string, unknown>,
  secret: string,
  ttlSecs = 60 * 60,
): Record<string, unknown> {
  const signed: Record<string, unknown> = {
    ...payload,
    exp: Math.floor(Date.now() / 1000) + ttlSecs,
  };
  signed.sig = hmacHex(stableStringify(signed), secret);
  return signed;
}

const FALLBACK_SECRET = "drivecare-voice-agent-prod-secret-change-me";

export function sessionSecret(): string {
  return (
    (process.env.SESSION_SECRET ?? process.env.AUTH_SECRET ?? "").trim() ||
    FALLBACK_SECRET
  );
}

export function authSecret(): string {
  return (
    (process.env.AUTH_SECRET ?? process.env.SESSION_SECRET ?? "").trim() ||
    FALLBACK_SECRET
  );
}

export function jwtIssuer(): string {
  return (process.env.JWT_ISSUER ?? "lumina").trim() || "lumina";
}

export function jwtAudience(): string {
  return (process.env.JWT_AUDIENCE ?? "lumina-app").trim() || "lumina-app";
}
