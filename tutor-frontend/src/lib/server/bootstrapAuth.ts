import { randomBytes } from "crypto";

import { mintAccessJwt } from "@/lib/server/jwt";
import { authSecret } from "@/lib/server/signing";

export const BOOTSTRAP_EMAIL = "abcd@gmail.com";
export const BOOTSTRAP_PASSWORD = "Abcdef@123";
export const BOOTSTRAP_USER_ID = "00000000-0000-4000-8000-abcd00000001";
export const BOOTSTRAP_ACCESS_TTL_SECS = 14 * 24 * 60 * 60;

export function isBootstrapCredentials(email: string, password: string): boolean {
  return email.trim().toLowerCase() === BOOTSTRAP_EMAIL && password === BOOTSTRAP_PASSWORD;
}

export function bootstrapTokens(): {
  access_token: string;
  refresh_token: string;
} | null {
  const secret = authSecret();
  return {
    access_token: mintAccessJwt(
      BOOTSTRAP_USER_ID,
      secret,
      BOOTSTRAP_ACCESS_TTL_SECS,
    ),
    refresh_token: randomBytes(32).toString("hex"),
  };
}
