import Link from "next/link";

export default function NotFound() {
  return (
    <main className="error-page">
      <h1>Page not found</h1>
      <p>That lesson or chapter is not in this catalog.</p>
      <Link className="btn btn-primary" href="/">
        Back to home
      </Link>
    </main>
  );
}
