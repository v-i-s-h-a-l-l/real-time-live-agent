import { notFound } from "next/navigation";

import { TopicList } from "@/components/curriculum/TopicList";
import { AppShell } from "@/components/layout/AppShell";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { subjectPath } from "@/lib/routes";
import { curriculumService } from "@/services/curriculum/CurriculumService";

export default async function ChapterPage({
  params,
}: {
  params: Promise<{ subjectId: string; chapterId: string }>;
}) {
  const { subjectId, chapterId } = await params;
  const subject = curriculumService.getSubject(subjectId);
  const chapter = curriculumService.getChapter(chapterId);

  if (!subject || !chapter || chapter.subjectId !== subject.id) {
    notFound();
  }

  const schoolClass = curriculumService.getClass(subject.classId);
  const topics = curriculumService.getTopics(chapter.id);

  return (
    <AppShell>
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: subject.name, href: subjectPath(subject.id) },
          { label: chapter.title },
        ]}
      />

      <header className="page-header">
        <p className="session-kicker">
          {schoolClass?.label} · {subject.name}
        </p>
        <h1 className="session-title">{chapter.title}</h1>
        <p className="session-chapter">{chapter.description}</p>
      </header>

      <section className="topic-section" aria-labelledby="topics-heading">
        <div className="section-head">
          <h2 id="topics-heading">Topics</h2>
          <p>Choose a topic to start learning with the tutor.</p>
        </div>
        <TopicList
          subjectId={subject.id}
          chapterId={chapter.id}
          topics={topics}
        />
      </section>
    </AppShell>
  );
}
