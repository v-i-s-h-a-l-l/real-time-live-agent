import Link from "next/link";
import type { ReactNode } from "react";

import { SignOutButton } from "@/components/auth/SignOutButton";
import { curriculumService } from "@/services/curriculum/CurriculumService";

const CLASS_LABEL =
  curriculumService.getClass("class-10")?.label ?? "Class 10";

export function AppShell({
  children,
  compact = false,
  wide = false,
  home = false,
}: {
  children: ReactNode;
  compact?: boolean;
  wide?: boolean;
  home?: boolean;
}) {
  return (
    <div
      className={`app-shell${wide ? " app-shell-wide" : ""}${home ? " app-shell-home" : ""}`}
    >
      <header className={`topbar ${compact ? "topbar-compact" : ""}`}>
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden />
          <span className="brand-text">
            <span className="brand-name">Lumina</span>
            <span className="brand-sub">{CLASS_LABEL} AI Tutor</span>
          </span>
        </Link>
        {home ? (
          <div className="topbar-actions">
            <p className="topbar-presence">
              AI Tutor
              <span className="topbar-presence-sep" aria-hidden>
                ·
              </span>
              <span className="topbar-presence-state">Ready</span>
            </p>
            <SignOutButton />
          </div>
        ) : (
          <SignOutButton />
        )}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
