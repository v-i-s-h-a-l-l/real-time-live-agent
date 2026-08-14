"use client";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="error-page">
      <h1>Something went wrong</h1>
      <p>Reload this lesson to continue. Your voice session will need to be started again.</p>
      <button type="button" className="btn btn-primary" onClick={() => reset()}>
        Reload lesson
      </button>
    </main>
  );
}
