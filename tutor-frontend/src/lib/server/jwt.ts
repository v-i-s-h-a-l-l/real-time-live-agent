import { createHmac, timingSafeEqual } from "crypto";

import { jwtAudience, jwtIssuer } from "@/lib/server/signing";

type AccessClaims = {
  sub: string;
  iss: string;
  aud: string;
  iat: number;
  exp: number;
  typ: string;
  jti?: string;
};

function b64urlJson(part: string): unknown {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
}

export function verifyAccessJwt(
  token: string,
  secret: string,
): AccessClaims | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [headerPart, payloadPart, signaturePart] = parts;
  const expected = createHmac("sha256", secret)
    .update(`${headerPart}.${payloadPart}`)
    .digest();
  let actual: Buffer;
  try {
    actual = Buffer.from(signaturePart, "base64url");
  } catch {
    return null;
  }
  if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) {
    return null;
  }
  let header: { alg?: string; typ?: string };
  let payload: AccessClaims;
  try {
    header = b64urlJson(headerPart) as { alg?: string; typ?: string };
    payload = b64urlJson(payloadPart) as AccessClaims;
  } catch {
    return null;
  }
  if (header.alg !== "HS256") return null;
  if (payload.typ !== "access") return null;
  if (typeof payload.sub !== "string" || !payload.sub) return null;
  if (payload.iss !== jwtIssuer()) return null;
  if (payload.aud !== jwtAudience()) return null;
  const now = Math.floor(Date.now() / 1000);
  if (typeof payload.exp !== "number" || payload.exp < now - 5) return null;
  return payload;
}
