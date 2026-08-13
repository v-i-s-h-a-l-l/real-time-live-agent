import Link from "next/link";
import type { ReactNode } from "react";

import { curriculumService } from "@/services/curriculum/CurriculumService";

const CLASS_LABEL =
  curriculumService.getClass("class-10")?.label ?? "Class 10";

export function AppShell({
  children,
  compact = false,
  wide = false,
}: {
  children: ReactNode;
  compact?: boolean;
  wide?: boolean;
}) {
  return (
    <div className={`app-shell${wide ? " app-shell-wide" : ""}`}>
      <header className={`topbar ${compact ? "topbar-compact" : ""}`}>
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden />
          <span className="brand-text">
            <span className="brand-name">Lumina</span>
            <span className="brand-sub">{CLASS_LABEL} AI Tutor</span>
          </span>
        </Link>
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
