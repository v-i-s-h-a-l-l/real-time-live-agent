/**
 * Next.js startup hook. Refuse to boot if signing secrets are missing.
 * Kept free of `crypto` so the instrumentation bundle does not pull Node
 * builtins into a webpack context that cannot resolve them.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "edge") {
    return;
  }
  const session = (process.env.SESSION_SECRET ?? "").trim();
  const auth = (process.env.AUTH_SECRET ?? "").trim();
  if (!session && !auth) {
    throw new Error(
      "SESSION_SECRET is missing (or empty). Set SESSION_SECRET or AUTH_SECRET " +
        "before starting — there is no default signing secret.",
    );
  }
}
