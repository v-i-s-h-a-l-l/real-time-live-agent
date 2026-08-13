import type {
  Chapter,
  CurriculumCatalog,
  SchoolClass,
  Subject,
  Topic,
} from "@/domain/curriculum/types";

import {
  LINEAR_EQUATIONS_CHAPTER,
  LINEAR_EQUATIONS_TOPICS,
} from "@/content/curriculum/class10/mathematics/chapters/pair-of-linear-equations";
import {
  POLYNOMIALS_CHAPTER,
  POLYNOMIALS_TOPICS,
} from "@/content/curriculum/class10/mathematics/chapters/polynomials";
import {
  QUADRATIC_EQUATIONS_CHAPTER,
  QUADRATIC_EQUATIONS_TOPICS,
} from "@/content/curriculum/class10/mathematics/chapters/quadratic-equations";
import {
  REAL_NUMBERS_CHAPTER,
  REAL_NUMBERS_TOPICS,
} from "@/content/curriculum/class10/mathematics/chapters/real-numbers";

const CLASS_10: SchoolClass = {
  id: "class-10",
  label: "Class 10",
  grade: 10,
  subjectIds: ["mathematics", "english"],
};

const MATHEMATICS: Subject = {
  id: "mathematics",
  classId: "class-10",
  name: "Mathematics",
  description:
    "Class 10 NCERT-aligned algebra foundations — numbers, polynomials, linear systems, and quadratics.",
  available: true,
  chapterIds: [
    REAL_NUMBERS_CHAPTER.id,
    POLYNOMIALS_CHAPTER.id,
    LINEAR_EQUATIONS_CHAPTER.id,
    QUADRATIC_EQUATIONS_CHAPTER.id,
  ],
};

const ENGLISH_PLACEHOLDER: Subject = {
  id: "english",
  classId: "class-10",
  name: "English",
  description: "Coming soon — reading, writing, and grammar.",
  available: false,
  chapterIds: [],
};

const CHAPTERS: Chapter[] = [
  REAL_NUMBERS_CHAPTER,
  POLYNOMIALS_CHAPTER,
  LINEAR_EQUATIONS_CHAPTER,
  QUADRATIC_EQUATIONS_CHAPTER,
];

const TOPICS: Topic[] = [
  ...REAL_NUMBERS_TOPICS,
  ...POLYNOMIALS_TOPICS,
  ...LINEAR_EQUATIONS_TOPICS,
  ...QUADRATIC_EQUATIONS_TOPICS,
];

/** Single source of truth for Class 10 curriculum data. */
export const CLASS10_CURRICULUM_CATALOG: CurriculumCatalog = {
  classes: [CLASS_10],
  subjects: [MATHEMATICS, ENGLISH_PLACEHOLDER],
  chapters: CHAPTERS,
  topics: TOPICS,
};
