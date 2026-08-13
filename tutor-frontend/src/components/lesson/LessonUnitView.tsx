"use client";

import type { LessonUnit } from "@/domain/lesson/lessonFlow";

export function LessonUnitView({ unit }: { unit: LessonUnit }) {
  return (
    <article className="lesson-unit" data-type={unit.type}>
      <p className="lesson-unit-type">{formatType(unit.type)}</p>
      <h2 className="lesson-unit-title">{unit.title}</h2>
      <p className="lesson-unit-body">{unit.body}</p>

      {unit.formulas.length > 0 ? (
        <ul className="formula-board" aria-label="Formulas">
          {unit.formulas.map((formula) => (
            <li key={formula}>{formula}</li>
          ))}
        </ul>
      ) : null}

      {unit.steps && unit.steps.length > 0 ? (
        <ol className="example-steps">
          {unit.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}

      {unit.answer ? (
        <p className="lesson-unit-answer">
          <strong>Answer.</strong> {unit.answer}
        </p>
      ) : null}

      {unit.keyPoints.length > 0 ? (
        <ul className="lesson-keypoints">
          {unit.keyPoints.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function formatType(type: LessonUnit["type"]): string {
  switch (type) {
    case "concept":
      return "Concept";
    case "formula":
      return "Formula";
    case "example":
      return "Worked example";
    case "mistake":
      return "Watch out";
    case "overview":
      return "Overview";
    default:
      return "Lesson";
  }
}
