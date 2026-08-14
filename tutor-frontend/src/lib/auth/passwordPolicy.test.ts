import { describe, expect, it } from "vitest";

import { passwordPolicyError } from "@/lib/auth/passwordPolicy";

describe("password policy", () => {
  it("accepts a strong password", () => {
    expect(passwordPolicyError("Abcd1234!")).toBeNull();
  });

  it("rejects weak passwords", () => {
    expect(passwordPolicyError("short1!")).toBe("weak_password");
    expect(passwordPolicyError("alllowercase1!")).toBe("weak_password");
    expect(passwordPolicyError("ALLUPPERCASE1!")).toBe("weak_password");
    expect(passwordPolicyError("NoDigits!!")).toBe("weak_password");
    expect(passwordPolicyError("NoSpecials1")).toBe("weak_password");
  });
});
