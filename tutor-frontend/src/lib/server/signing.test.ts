import { afterEach, describe, expect, it, vi } from "vitest";

import { authSecret, sessionSecret } from "@/lib/server/signing";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("signing secrets", () => {
  it("uses SESSION_SECRET and AUTH_SECRET without a default", () => {
    vi.stubEnv("SESSION_SECRET", "session-value");
    vi.stubEnv("AUTH_SECRET", "auth-value");
    expect(sessionSecret()).toBe("session-value");
    expect(authSecret()).toBe("auth-value");
  });

  it("falls back across the two env vars, still with no hardcoded secret", () => {
    vi.stubEnv("SESSION_SECRET", "");
    vi.stubEnv("AUTH_SECRET", "only-auth");
    expect(sessionSecret()).toBe("only-auth");
    vi.stubEnv("AUTH_SECRET", "");
    vi.stubEnv("SESSION_SECRET", "only-session");
    expect(authSecret()).toBe("only-session");
  });

  it("throws when both secrets are missing", () => {
    vi.stubEnv("SESSION_SECRET", "");
    vi.stubEnv("AUTH_SECRET", "");
    expect(() => sessionSecret()).toThrow(/SESSION_SECRET/);
    expect(() => authSecret()).toThrow(/AUTH_SECRET/);
  });
});
