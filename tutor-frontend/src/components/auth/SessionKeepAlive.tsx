"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

const PUBLIC = new Set(["/signin", "/signup"]);

/** Quietly rotate the access cookie while a refresh session exists. */
export function SessionKeepAlive() {
  const pathname = usePathname();

  useEffect(() => {
    if (PUBLIC.has(pathname)) return;
    const run = () => {
      void fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
      });
    };
    run();
    const id = window.setInterval(run, 10 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [pathname]);

  return null;
}
