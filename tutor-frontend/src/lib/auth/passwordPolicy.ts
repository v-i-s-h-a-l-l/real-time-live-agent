export const PASSWORD_MIN_LEN = 8;
export const PASSWORD_MAX_LEN = 128;

const UPPER = /[A-Z]/;
const LOWER = /[a-z]/;
const DIGIT = /[0-9]/;
const SPECIAL = /[^A-Za-z0-9]/;

export const PASSWORD_REQUIREMENTS = [
  "At least 8 characters",
  "One uppercase letter",
  "One lowercase letter",
  "One number",
  "One special character",
] as const;

export function passwordPolicyError(password: string): string | null {
  if (
    password.length < PASSWORD_MIN_LEN ||
    password.length > PASSWORD_MAX_LEN
  ) {
    return "weak_password";
  }
  if (!UPPER.test(password)) return "weak_password";
  if (!LOWER.test(password)) return "weak_password";
  if (!DIGIT.test(password)) return "weak_password";
  if (!SPECIAL.test(password)) return "weak_password";
  return null;
}

export function emailLooksValid(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
