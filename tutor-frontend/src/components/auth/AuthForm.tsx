"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  emailLooksValid,
  PASSWORD_REQUIREMENTS,
  passwordPolicyError,
} from "@/lib/auth/passwordPolicy";

function errorCopy(code: string): string {
  if (code === "weak_password") {
    return "Use 8+ characters with upper, lower, number, and a symbol.";
  }
  if (code === "password_mismatch") {
    return "Passwords do not match.";
  }
  if (code === "invalid_email") {
    return "Enter a valid email address.";
  }
  if (code === "rate_limited" || code === "429") {
    return "Too many attempts. Please wait and try again.";
  }
  if (code === "check_your_email") {
    return "If you already have an account, sign in with that email instead.";
  }
  if (code === "could_not_create") {
    return "Could not create an account. Try a different email.";
  }
  if (code === "server_unavailable") {
    return "The learning space is not reachable right now. Try again in a moment.";
  }
  return "Could not sign in. Check your email and password.";
}

export function AuthForm({ mode }: { mode: "signin" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    if (!emailLooksValid(email)) {
      setError(errorCopy("invalid_email"));
      return;
    }
    if (isSignup && passwordPolicyError(password)) {
      setError(errorCopy("weak_password"));
      return;
    }
    if (isSignup && password !== confirmPassword) {
      setError(errorCopy("password_mismatch"));
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(
        isSignup ? "/api/auth/signup" : "/api/auth/signin",
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            isSignup
              ? { email, password, confirmPassword }
              : { email, password },
          ),
        },
      );
      if (response.status === 429) {
        setError(errorCopy("rate_limited"));
        return;
      }
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as {
          error?: string;
        } | null;
        setError(errorCopy(data?.error ?? "invalid_credentials"));
        return;
      }
      router.replace("/");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <header className="auth-brand">
        <span className="brand-mark" aria-hidden />
        <span className="brand-text">
          <span className="brand-name">Lumina</span>
          <span className="brand-sub">Class 10 AI Tutor</span>
        </span>
      </header>
      <section className="auth-card">
        <h1 className="auth-title">
          {isSignup ? "Create your account" : "Welcome back"}
        </h1>
        <p className="auth-lead">
          {isSignup
            ? "Sign up with email to enter your Class 10 learning space."
            : "Sign in to continue learning with your tutor."}
        </p>
        <form className="auth-form" onSubmit={onSubmit}>
          <label className="auth-field">
            Email
            <input
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="auth-field">
            Password
            <input
              type="password"
              name="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={isSignup ? 8 : 1}
              maxLength={128}
            />
          </label>
          {isSignup ? (
            <>
              <label className="auth-field">
                Confirm password
                <input
                  type="password"
                  name="confirmPassword"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={8}
                  maxLength={128}
                />
              </label>
              <ul className="auth-requirements">
                {PASSWORD_REQUIREMENTS.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? "Please wait…" : isSignup ? "Sign up" : "Sign in"}
          </button>
        </form>
        <p className="auth-switch">
          {isSignup ? (
            <>
              Already have an account? <Link href="/signin">Sign in</Link>
            </>
          ) : (
            <>
              New here? <Link href="/signup">Sign up</Link>
            </>
          )}
        </p>
      </section>
    </div>
  );
}
