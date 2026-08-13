import { AppShell } from "@/components/layout/AppShell";
import { SubjectCard } from "@/components/dashboard/SubjectCard";
import { curriculumService } from "@/services/curriculum/CurriculumService";

const CLASS_ID = "class-10";

export default function DashboardPage() {
  const schoolClass = curriculumService.getClass(CLASS_ID);
  const subjects = curriculumService.getSubjects(CLASS_ID);

  return (
    <AppShell>
      <section className="hero">
        <p className="hero-eyebrow">{schoolClass?.label ?? "Class 10"}</p>
        <h1 className="hero-brand">Lumina</h1>
        <p className="hero-lead">
          A calm Class 10 workspace. Learn from the lesson, then talk or type to
          your tutor — it always knows what is on your screen.
        </p>
      </section>

      <section className="subjects" aria-labelledby="subjects-heading">
        <div className="section-head">
          <h2 id="subjects-heading">Choose a subject</h2>
          <p>Mathematics is ready. More subjects will unlock as content lands.</p>
        </div>
        <div className="subject-grid">
          {subjects.map((subject) => (
            <SubjectCard key={subject.id} subject={subject} />
          ))}
        </div>
      </section>
    </AppShell>
  );
}
