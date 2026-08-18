import { describe, expect, it } from "vitest";

import { mintAccessJwt, verifyAccessJwt } from "@/lib/server/jwt";
import { createHmac } from "crypto";

const SECRET = "test-auth-secret-value-32chars-min";

function b64url(value: string): string {
  return Buffer.from(value).toString("base64url");
}

function mint(payload: Record<string, unknown>, secret = SECRET): string {
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64url(JSON.stringify(payload));
  const sig = createHmac("sha256", secret)
    .update(`${header}.${body}`)
    .digest("base64url");
  return `${header}.${body}.${sig}`;
}

describe("access JWT verification", () => {
  const valid = {
    sub: "user-1",
    iss: "lumina",
    aud: "lumina-app",
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 900,
    typ: "access",
    jti: "abc",
  };

  it("accepts a well-formed access token", () => {
    expect(verifyAccessJwt(mint(valid), SECRET)?.sub).toBe("user-1");
  });

  it("rejects the wrong issuer, audience, type, and secret", () => {
    expect(verifyAccessJwt(mint({ ...valid, iss: "evil" }), SECRET)).toBeNull();
    expect(verifyAccessJwt(mint({ ...valid, aud: "other" }), SECRET)).toBeNull();
    expect(verifyAccessJwt(mint({ ...valid, typ: "refresh" }), SECRET)).toBeNull();
    expect(verifyAccessJwt(mint(valid), "other-secret")).toBeNull();
  });

  it("round-trips mintAccessJwt", () => {
    const token = mintAccessJwt("user-1", SECRET, 900);
    expect(verifyAccessJwt(token, SECRET)?.sub).toBe("user-1");
  });
});
