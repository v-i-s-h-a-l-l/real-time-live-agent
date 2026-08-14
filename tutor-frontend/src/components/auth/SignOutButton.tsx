"use client";

import { useRouter } from "next/navigation";

export function SignOutButton() {
  const router = useRouter();

  async function onClick(): Promise<void> {
    await fetch("/api/auth/signout", {
      method: "POST",
      credentials: "same-origin",
    });
    router.replace("/signin");
    router.refresh();
  }

  return (
    <button type="button" className="signout-btn" onClick={() => void onClick()}>
      Sign out
    </button>
  );
}
