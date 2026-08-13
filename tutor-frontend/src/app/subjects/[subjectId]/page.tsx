import Link from "next/link";
import { notFound } from "next/navigation";

import { ChapterList } from "@/components/dashboard/ChapterList";
import { AppShell } from "@/components/layout/AppShell";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { curriculumService } from "@/services/curriculum/CurriculumService";

export default async function SubjectPage({
  params,
}: {
  params: Promise<{ subjectId: string }>;
}) {
  const { subjectId } = await params;
  const subject = curriculumService.getSubject(subjectId);
  if (!subject) notFound();

  const schoolClass = curriculumService.getClass(subject.classId);
  const chapters = curriculumService.getChapters(subject.id);

  return (
    <AppShell>
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: schoolClass?.label ?? "Class", href: "/" },
          { label: subject.name },
        ]}
      />

      <header className="page-header">
        <p className="session-kicker">{schoolClass?.label}</p>
        <h1 className="session-title">{subject.name}</h1>
        <p className="session-chapter">{subject.description}</p>
        {!subject.available ? (
          <p className="empty-state">This subject is not available yet.</p>
        ) : null}
      </header>

      {subject.available ? (
        <ChapterList subjectId={subject.id} chapters={chapters} />
      ) : (
        <Link href="/" className="btn btn-ghost">
          ← Back to dashboard
        </Link>
      )}
    </AppShell>
  );
}
