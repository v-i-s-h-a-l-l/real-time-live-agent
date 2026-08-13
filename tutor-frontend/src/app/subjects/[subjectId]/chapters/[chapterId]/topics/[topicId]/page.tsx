import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { LessonExperience } from "@/components/lesson/LessonExperience";
import { chapterPath, subjectPath } from "@/lib/routes";
import { curriculumService } from "@/services/curriculum/CurriculumService";

export default async function TopicPage({
  params,
}: {
  params: Promise<{ subjectId: string; chapterId: string; topicId: string }>;
}) {
  const { subjectId, chapterId, topicId } = await params;
  const subject = curriculumService.getSubject(subjectId);
  const chapter = curriculumService.getChapter(chapterId);
  const topic = curriculumService.getTopic(topicId);
  const sessionContext = curriculumService.tryCreateSessionContext(topicId);

  if (
    !subject ||
    !chapter ||
    !topic ||
    !sessionContext ||
    chapter.subjectId !== subject.id ||
    topic.chapterId !== chapter.id
  ) {
    notFound();
  }

  return (
    <AppShell compact wide>
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: subject.name, href: subjectPath(subject.id) },
          {
            label: chapter.title,
            href: chapterPath(subject.id, chapter.id),
          },
          { label: topic.title },
        ]}
      />

      <LessonExperience topic={topic} sessionContext={sessionContext} />
    </AppShell>
  );
}
