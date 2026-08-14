import { ComingSoonCard } from "@/components/dashboard/ComingSoonCard";
import { ContinueLearningCard } from "@/components/dashboard/ContinueLearningCard";
import { SubjectCard } from "@/components/dashboard/SubjectCard";
import { TutorCallout } from "@/components/dashboard/TutorCallout";
import { WelcomeSection } from "@/components/dashboard/WelcomeSection";
import { AppShell } from "@/components/layout/AppShell";
import { topicPath } from "@/lib/routes";
import { curriculumService } from "@/services/curriculum/CurriculumService";

const CLASS_ID = "class-10";

function compactChapterLabel(title: string): string {
  if (/linear/i.test(title)) return "Linear equations";
  if (/quadratic/i.test(title)) return "Quadratics";
  if (/real number/i.test(title)) return "Numbers";
  return title;
}

export default function DashboardPage() {
  const schoolClass = curriculumService.getClass(CLASS_ID);
  const classLabel = schoolClass?.label ?? "Class 10";
  const subjects = curriculumService.getSubjects(CLASS_ID);
  const startSubject = subjects.find((subject) => subject.available);
  const chapters = startSubject
    ? curriculumService.getChapters(startSubject.id)
    : [];
  const firstChapter = chapters[0] ?? null;
  const firstTopic = firstChapter
    ? (curriculumService.getTopics(firstChapter.id)[0] ?? null)
    : null;
  const lessonHref =
    startSubject && firstChapter && firstTopic
      ? topicPath(startSubject.id, firstChapter.id, firstTopic.id)
      : null;
  const chapterTrail = chapters
    .slice(0, 2)
    .map((chapter) => chapter.title)
    .join(" · ");

  return (
    <AppShell home>
      <div className="home-page">
        <WelcomeSection />

        {startSubject && firstChapter && firstTopic && lessonHref ? (
          <ContinueLearningCard
            subjectName={startSubject.name}
            chapterTitle={firstChapter.title}
            topicTitle={firstTopic.title}
            trail={chapterTrail}
            href={lessonHref}
            chapterOrder={firstChapter.order}
          />
        ) : null}

        <section className="home-subjects" aria-labelledby="subjects-heading">
          <div className="section-head">
            <h2 id="subjects-heading">Your subjects</h2>
            <p>Explore your {classLabel} curriculum.</p>
          </div>
          <div className="subject-grid">
            {subjects.map((subject) =>
              subject.available ? (
                <SubjectCard
                  key={subject.id}
                  subject={subject}
                  chapterCount={
                    curriculumService.getChapters(subject.id).length
                  }
                  classLabel={classLabel}
                  focus={curriculumService
                    .getChapters(subject.id)
                    .map((chapter) => compactChapterLabel(chapter.title))
                    .join(" · ")}
                />
              ) : (
                <ComingSoonCard key={subject.id} subject={subject} />
              ),
            )}
          </div>
        </section>

        {lessonHref ? <TutorCallout href={lessonHref} /> : null}

        <footer className="home-footer">
          <p>Lumina · {classLabel} learning space</p>
        </footer>
      </div>
    </AppShell>
  );
}
