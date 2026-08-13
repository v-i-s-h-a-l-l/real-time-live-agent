import type { Chapter, Topic } from "@/domain/curriculum/types";

export const QUADRATIC_EQUATIONS_CHAPTER: Chapter = {
  id: "quadratic-equations",
  subjectId: "mathematics",
  title: "Quadratic Equations",
  description:
    "Standard form, factorisation, the quadratic formula, and the discriminant — core Class 10 algebra.",
  order: 4,
  topicIds: [
    "standard-form-quadratic",
    "factorisation-quadratic",
    "quadratic-formula",
    "discriminant",
  ],
};

const STANDARD_FORM: Topic = {
  id: "standard-form-quadratic",
  chapterId: "quadratic-equations",
  title: "Standard Form",
  shortDescription:
    "Recognise and rewrite equations as ax² + bx + c = 0 with a ≠ 0, then identify a, b and c.",
  learningObjectives: [
    "Rewrite any quadratic equation into standard form",
    "Identify coefficients a, b and c correctly (including signs)",
    "Explain why a cannot be zero",
  ],
  prerequisites: ["Algebraic expressions", "Linear equations in one variable"],
  conceptNotes: [
    {
      id: "what-is-quadratic",
      title: "What makes an equation quadratic?",
      body: "A quadratic equation involves a variable to the power 2 as its highest power. After rearranging, it looks like ax² + bx + c = 0 where a, b, c are real numbers and a is not zero. If a were zero, the x² term disappears and you are left with a linear equation.",
    },
    {
      id: "reading-coefficients",
      title: "Reading a, b and c",
      body: "Bring every term to one side so the other side is 0. Then: a is the coefficient of x², b is the coefficient of x, and c is the constant term. Missing terms still count — if there is no x term, b = 0; if there is no constant, c = 0.",
    },
    {
      id: "why-standard-form",
      title: "Why standard form matters",
      body: "Factorisation, the quadratic formula and the discriminant all assume the equation is already in ax² + bx + c = 0. Spending ten seconds on rearranging prevents sign errors later.",
    },
  ],
  keyPoints: [
    "Highest power must be exactly 2",
    "Always rearrange to = 0 before reading a, b, c",
    "a ≠ 0; b or c may be zero",
    "Watch signs carefully when moving terms across the equals sign",
  ],
  formulas: ["ax² + bx + c = 0,  a ≠ 0"],
  examples: [
    {
      id: "sf-ex-1",
      title: "Rearrange and identify coefficients",
      question: "Write 3x = 2x² − 5 in standard form and state a, b, c.",
      steps: [
        "Move all terms to one side: 0 = 2x² − 3x − 5.",
        "Rewrite as 2x² − 3x − 5 = 0.",
        "Read coefficients: a = 2, b = −3, c = −5.",
      ],
      answer: "2x² − 3x − 5 = 0; a = 2, b = −3, c = −5",
      explanation:
        "Subtracting 3x from both sides of 3x = 2x² − 5 gives the standard form. The minus signs on b and c come directly from the rearranged expression.",
      commonMistake: "Writing b = 3 instead of b = −3 after moving 3x.",
    },
    {
      id: "sf-ex-2",
      title: "Expand first",
      question: "Is (x − 1)(x + 4) = 0 quadratic? If so, find a, b, c.",
      steps: [
        "Expand: x² + 4x − x − 4 = x² + 3x − 4.",
        "Write x² + 3x − 4 = 0.",
        "Identify a = 1, b = 3, c = −4.",
      ],
      answer: "Yes; a = 1, b = 3, c = −4",
      explanation:
        "Factored form is still quadratic once expanded. Expanding reveals the coefficients the formula needs.",
    },
  ],
  commonMistakes: [
    "Leaving terms on both sides and misreading signs of b and c",
    "Calling a linear equation like 2x + 3 = 0 a quadratic",
    "Forgetting that a missing x term means b = 0, not that b does not exist",
  ],
  hints: [
    "Move every term to the left side first",
    "Check that the highest power of x is exactly 2",
    "Rewrite fractions so all coefficients are clear",
  ],
  practiceQuestions: [
    {
      id: "sf-pq-1",
      question: "Write x(x − 5) = 6 in standard form.",
      difficulty: "easy",
      style: "direct",
      hints: ["Expand the left side first", "Subtract 6 from both sides"],
      expectedAnswer: "x^2 - 5x - 6 = 0",
      acceptedAnswers: ["x² − 5x − 6 = 0", "x² - 5x - 6 = 0"],
      solution: [
        "Expand: x² − 5x = 6.",
        "Subtract 6: x² − 5x − 6 = 0.",
      ],
      conceptNoteIds: ["reading-coefficients"],
    },
    {
      id: "sf-pq-2",
      question: "For 5 − 2x² = 3x, find a, b, c after writing standard form.",
      difficulty: "medium",
      style: "multi-step",
      hints: ["Bring all terms to one side", "You may multiply by −1 if you prefer a > 0"],
      expectedAnswer: "a = -2, b = -3, c = 5 (or a = 2, b = 3, c = -5)",
      acceptedAnswers: [
        "a=-2, b=-3, c=5",
        "a=2, b=3, c=-5",
        "-2x^2 - 3x + 5 = 0",
        "2x^2 + 3x - 5 = 0",
      ],
      solution: [
        "Rearrange: −2x² − 3x + 5 = 0.",
        "So a = −2, b = −3, c = 5.",
        "Equivalently multiply by −1: 2x² + 3x − 5 = 0.",
      ],
    },
    {
      id: "sf-pq-3",
      question: "Why is 4x + 7 = 0 not a quadratic equation?",
      difficulty: "easy",
      style: "conceptual",
      hints: ["Look at the highest power of x"],
      expectedAnswer: "There is no x^2 term (a = 0), so it is linear",
      acceptedAnswers: [
        "no x^2 term",
        "it is linear",
        "highest power is 1",
        "a = 0",
      ],
      solution: [
        "A quadratic needs a non-zero x² term.",
        "Here the highest power is 1, so the equation is linear.",
      ],
    },
    {
      id: "sf-pq-4",
      question:
        "A student writes x² = 5x − 6 as a = 1, b = 5, c = −6. What went wrong?",
      difficulty: "medium",
      style: "error-identification",
      hints: ["Move all terms to one side before reading b"],
      expectedAnswer: "They did not rearrange to = 0; correct is b = -5, c = 6",
      acceptedAnswers: [
        "b should be -5 and c should be 6",
        "must move terms: x^2 - 5x + 6 = 0",
      ],
      solution: [
        "Correct form: x² − 5x + 6 = 0.",
        "So a = 1, b = −5, c = 6.",
        "The student kept 5x on the right and misread the sign of b.",
      ],
    },
    {
      id: "sf-pq-5",
      question: "Write (2x − 1)/3 = x² in standard form with integer coefficients.",
      difficulty: "hard",
      style: "exam-style",
      hints: ["Multiply both sides by 3", "Bring all terms to one side"],
      expectedAnswer: "3x^2 - 2x + 1 = 0",
      acceptedAnswers: ["3x² − 2x + 1 = 0", "3x^2 - 2x + 1 = 0"],
      solution: [
        "Multiply by 3: 2x − 1 = 3x².",
        "Rearrange: 0 = 3x² − 2x + 1.",
        "Standard form: 3x² − 2x + 1 = 0.",
      ],
    },
  ],
  difficulty: "easy",
  relatedTopicIds: ["factorisation-quadratic", "quadratic-formula"],
  estimatedMinutes: 20,
};

const FACTORISATION: Topic = {
  id: "factorisation-quadratic",
  chapterId: "quadratic-equations",
  title: "Factorisation",
  shortDescription:
    "Solve ax² + bx + c = 0 by writing it as a product of linear factors and using the zero-product property.",
  learningObjectives: [
    "Factorise simple and moderate quadratics",
    "Apply the zero-product property correctly",
    "Decide when factorisation is practical versus using the formula",
  ],
  prerequisites: ["Standard form", "Factoring linear expressions"],
  conceptNotes: [
    {
      id: "zero-product",
      title: "Zero-product property",
      body: "If a product AB equals zero, then at least one of A or B is zero. So if (x − 2)(x − 3) = 0, either x − 2 = 0 or x − 3 = 0. This is why factorisation turns one quadratic into two easy linear equations.",
    },
    {
      id: "middle-term-split",
      title: "Splitting the middle term",
      body: "For ax² + bx + c, find two numbers that multiply to ac and add to b. Rewrite bx as the sum of those two terms, then factor by grouping. If no such integers exist, factorisation over the integers will not work — use the quadratic formula instead.",
    },
  ],
  keyPoints: [
    "Factor → set each factor to zero → solve",
    "Numbers for splitting: product ac, sum b",
    "Not every quadratic factorises nicely over integers",
    "Always verify roots in the original equation",
  ],
  formulas: ["If AB = 0 then A = 0 or B = 0"],
  examples: [
    {
      id: "fac-ex-1",
      title: "Monic quadratic",
      question: "Solve x² − 5x + 6 = 0 by factorisation.",
      steps: [
        "Find two numbers with product 6 and sum −5: −2 and −3.",
        "Factor: (x − 2)(x − 3) = 0.",
        "So x − 2 = 0 or x − 3 = 0.",
      ],
      answer: "x = 2 or x = 3",
      explanation:
        "Because the quadratic is monic, the factors are easy to guess. Each factor gives one root.",
      commonMistake: "Writing (x + 2)(x + 3) after seeing sum −5.",
    },
    {
      id: "fac-ex-2",
      title: "Split the middle term",
      question: "Solve 2x² + 7x + 3 = 0.",
      steps: [
        "ac = 6; numbers 6 and 1 add to 7.",
        "Rewrite: 2x² + 6x + x + 3 = 0.",
        "Group: 2x(x + 3) + 1(x + 3) = (2x + 1)(x + 3) = 0.",
        "Roots: x = −1/2 or x = −3.",
      ],
      answer: "x = -1/2 or x = -3",
      explanation:
        "Grouping works once the middle term is split correctly. Each linear factor yields one solution.",
    },
  ],
  commonMistakes: [
    "Setting each factor equal to the constant instead of zero",
    "Forcing integer factors when none exist",
    "Sign errors when listing factor pairs of ac",
  ],
  hints: [
    "List factor pairs of ac systematically",
    "If no integer pair sums to b, switch to the formula",
    "Check roots by substitution",
  ],
  practiceQuestions: [
    {
      id: "fac-pq-1",
      question: "Solve x² + 5x + 6 = 0 by factorisation.",
      difficulty: "easy",
      style: "direct",
      hints: ["Find two numbers that multiply to 6 and add to 5"],
      expectedAnswer: "x = -2 or x = -3",
      acceptedAnswers: ["x=-2, x=-3", "-2 and -3"],
      solution: ["(x + 2)(x + 3) = 0", "x = −2 or x = −3"],
    },
    {
      id: "fac-pq-2",
      question: "Solve 3x² − 5x − 2 = 0 by factorisation.",
      difficulty: "medium",
      style: "multi-step",
      hints: ["ac = −6; try pairs whose sum is −5"],
      expectedAnswer: "x = 2 or x = -1/3",
      acceptedAnswers: ["x=2, x=-1/3", "2 and -1/3"],
      solution: [
        "Split: 3x² − 6x + x − 2 = 0.",
        "3x(x − 2) + 1(x − 2) = (3x + 1)(x − 2) = 0.",
        "x = 2 or x = −1/3.",
      ],
    },
    {
      id: "fac-pq-3",
      question:
        "Why might factorisation fail for x² − 4x + 1 = 0 even though roots exist?",
      difficulty: "medium",
      style: "reasoning",
      hints: ["Think about whether integer factors of 1 can sum to −4"],
      expectedAnswer:
        "No integer pair multiplies to 1 and adds to -4; roots are irrational",
      acceptedAnswers: [
        "does not factor over integers",
        "roots involve surds",
        "use quadratic formula instead",
      ],
      solution: [
        "Factor pairs of 1 are ±1 only; they cannot sum to −4.",
        "The discriminant is 12, so roots are real but irrational.",
        "Use the quadratic formula instead of integer factorisation.",
      ],
    },
    {
      id: "fac-pq-4",
      question: "A student solves (x − 4)(x + 1) = 5 by writing x = 4 or x = −1. Explain the error.",
      difficulty: "hard",
      style: "error-identification",
      hints: ["Zero-product needs the product equal to zero"],
      expectedAnswer:
        "They treated it as = 0; must expand/rearrange to standard form first",
      acceptedAnswers: [
        "right side is not zero",
        "must bring to = 0 before factoring",
      ],
      solution: [
        "Zero-product applies only when the product equals 0.",
        "Expand: x² − 3x − 4 = 5 → x² − 3x − 9 = 0, then solve.",
      ],
    },
    {
      id: "fac-pq-5",
      question: "Factorise and solve x² − 2x − 15 = 0.",
      difficulty: "easy",
      style: "direct",
      hints: ["Numbers with product −15 and sum −2"],
      expectedAnswer: "x = 5 or x = -3",
      acceptedAnswers: ["x=5, x=-3", "(x-5)(x+3)=0"],
      solution: ["(x − 5)(x + 3) = 0", "x = 5 or x = −3"],
    },
  ],
  difficulty: "medium",
  relatedTopicIds: ["standard-form-quadratic", "quadratic-formula", "discriminant"],
  estimatedMinutes: 30,
};

const QUADRATIC_FORMULA: Topic = {
  id: "quadratic-formula",
  chapterId: "quadratic-equations",
  title: "Quadratic Formula",
  shortDescription:
    "Solve any quadratic with x = (−b ± √(b² − 4ac)) / (2a), with careful substitution and simplification.",
  learningObjectives: [
    "State the quadratic formula from memory",
    "Substitute a, b, c carefully including signs",
    "Simplify exact answers involving radicals",
    "Choose formula vs factorisation appropriately",
  ],
  prerequisites: ["Standard form", "Square roots", "Discriminant (can be learned together)"],
  conceptNotes: [
    {
      id: "qf-purpose",
      title: "Why the quadratic formula exists",
      body: "Factorisation is fast when integers cooperate, but many Class 10 equations do not factor nicely. The quadratic formula always works for ax² + bx + c = 0 with a ≠ 0. It comes from completing the square, packed into one expression.",
    },
    {
      id: "qf-formula",
      title: "The formula",
      body: "x = (−b ± √(b² − 4ac)) / (2a). The expression under the root, Δ = b² − 4ac, is the discriminant. The ± gives two candidate roots. Always divide the entire (−b ± √Δ) by 2a — not only the square-root part.",
    },
    {
      id: "qf-substitute",
      title: "How to substitute safely",
      body: "Write a, b, c on paper first, including minus signs. Compute Δ next. Then substitute into the formula. If b is already negative, −b becomes positive — this is the most common slip.",
    },
    {
      id: "qf-simplify",
      title: "Simplifying answers",
      body: "If Δ is a perfect square, roots are rational (for rational a, b, c). If Δ = 12 = 4·3, write √12 = 2√3 and cancel common factors with the denominator. Leave answers in simplest surd form when required.",
    },
    {
      id: "qf-and-roots",
      title: "Link to nature of roots",
      body: "Δ > 0 → two distinct real roots; Δ = 0 → one repeated real root (the ± collapses); Δ < 0 → no real roots in the Class 10 real-number focus. The formula and discriminant work together.",
    },
  ],
  keyPoints: [
    "Formula: x = (−b ± √(b² − 4ac)) / (2a)",
    "List a, b, c before substituting",
    "Compute Δ first",
    "Divide the whole (−b ± √Δ) by 2a",
    "Simplify surds when possible",
  ],
  formulas: ["x = (−b ± √(b² − 4ac)) / (2a)", "Δ = b² − 4ac"],
  examples: [
    {
      id: "qf-ex-1",
      title: "Integer roots",
      question: "Solve x² − 5x + 6 = 0 using the quadratic formula.",
      steps: [
        "Identify a = 1, b = −5, c = 6.",
        "Compute Δ = (−5)² − 4(1)(6) = 25 − 24 = 1.",
        "x = (5 ± 1) / 2.",
        "So x = 6/2 = 3 or x = 4/2 = 2.",
      ],
      answer: "x = 3 or x = 2",
      explanation:
        "Even when factorisation works, the formula should give the same roots. Here Δ = 1 makes the arithmetic clean.",
      commonMistake: "Using b = 5 instead of b = −5 from x² − 5x + 6.",
    },
    {
      id: "qf-ex-2",
      title: "Watch the signs",
      question: "Solve 2x² − 3x − 2 = 0.",
      steps: [
        "a = 2, b = −3, c = −2.",
        "Δ = 9 − 4(2)(−2) = 9 + 16 = 25.",
        "x = (3 ± 5) / 4.",
        "x = 8/4 = 2 or x = −2/4 = −1/2.",
      ],
      answer: "x = 2 or x = -1/2",
      explanation:
        "Because c is negative, −4ac becomes positive and enlarges Δ. Tracking signs prevents an incorrect discriminant.",
    },
    {
      id: "qf-ex-3",
      title: "Surd form",
      question: "Solve x² − 4x + 1 = 0.",
      steps: [
        "a = 1, b = −4, c = 1.",
        "Δ = 16 − 4 = 12.",
        "x = (4 ± √12) / 2 = (4 ± 2√3) / 2.",
        "Simplify: x = 2 ± √3.",
      ],
      answer: "x = 2 ± √3",
      explanation:
        "√12 simplifies to 2√3, which cancels with the denominator 2. Leaving √12 unsimplified is incomplete.",
    },
    {
      id: "qf-ex-4",
      title: "Word problem setup",
      question:
        "The product of two consecutive positive integers is 56. Find the integers using a quadratic equation.",
      steps: [
        "Let the integers be n and n + 1.",
        "Then n(n + 1) = 56 → n² + n − 56 = 0.",
        "a = 1, b = 1, c = −56; Δ = 1 + 224 = 225.",
        "n = (−1 ± 15) / 2 → n = 7 or n = −8.",
        "Positive integers: 7 and 8.",
      ],
      answer: "7 and 8",
      explanation:
        "Modelling comes first; the formula is only the solving tool. Discard the negative root because the problem asks for positive integers.",
      commonMistake: "Keeping n = −8 without checking the positivity condition.",
    },
  ],
  commonMistakes: [
    "Dropping the minus in −b when b is already negative",
    "Dividing only ±√Δ by 2a and forgetting −b",
    "Computing Δ with the wrong sign on c",
    "Leaving √12 instead of simplifying to 2√3",
  ],
  hints: [
    "Write a, b, c before substituting",
    "Compute Δ first — it tells you what to expect",
    "If Δ is a perfect square, expect rational roots (for rational coefficients)",
  ],
  practiceQuestions: [
    {
      id: "qf-pq-1",
      question: "Solve x² − 7x + 10 = 0 using the quadratic formula.",
      difficulty: "easy",
      style: "direct",
      hints: ["a = 1, b = −7, c = 10", "Δ = 49 − 40"],
      expectedAnswer: "x = 5 or x = 2",
      acceptedAnswers: ["x=5, x=2", "5 and 2"],
      solution: [
        "Δ = 49 − 40 = 9.",
        "x = (7 ± 3) / 2 → x = 5 or x = 2.",
      ],
      conceptNoteIds: ["qf-substitute"],
    },
    {
      id: "qf-pq-2",
      question: "Solve 3x² + 2x − 1 = 0 using the formula.",
      difficulty: "medium",
      style: "direct",
      hints: ["Δ = 4 + 12 = 16"],
      expectedAnswer: "x = 1/3 or x = -1",
      acceptedAnswers: ["x=1/3, x=-1", "1/3 and -1"],
      solution: [
        "a = 3, b = 2, c = −1.",
        "x = (−2 ± 4) / 6.",
        "x = 2/6 = 1/3 or x = −6/6 = −1.",
      ],
    },
    {
      id: "qf-pq-3",
      question: "Solve x² + 4x + 1 = 0 and leave answers in surd form.",
      difficulty: "medium",
      style: "multi-step",
      hints: ["Δ = 16 − 4 = 12", "Simplify √12"],
      expectedAnswer: "x = -2 ± √3",
      acceptedAnswers: ["x=-2±√3", "-2 + √3 and -2 - √3"],
      solution: [
        "x = (−4 ± √12) / 2 = (−4 ± 2√3) / 2.",
        "x = −2 ± √3.",
      ],
      conceptNoteIds: ["qf-simplify"],
    },
    {
      id: "qf-pq-4",
      question:
        "A student writes x = −b ± √Δ / 2a for x² − 6x + 5 = 0. What is wrong, and what are the roots?",
      difficulty: "hard",
      style: "error-identification",
      hints: ["Order of operations: division applies to the whole numerator"],
      expectedAnswer:
        "Must divide entire (-b ± √Δ) by 2a; roots are x = 5 or x = 1",
      acceptedAnswers: [
        "x=5 or x=1",
        "division applies to whole numerator; roots 5 and 1",
      ],
      solution: [
        "Correct: x = (−b ± √Δ) / (2a).",
        "Here Δ = 36 − 20 = 16.",
        "x = (6 ± 4) / 2 → x = 5 or x = 1.",
      ],
    },
    {
      id: "qf-pq-5",
      question: "Without solving fully, explain why x² + x + 1 = 0 has no real roots.",
      difficulty: "easy",
      style: "conceptual",
      hints: ["Compute Δ = b² − 4ac"],
      expectedAnswer: "Δ = 1 - 4 = -3 < 0, so no real roots",
      acceptedAnswers: ["discriminant negative", "Δ < 0", "no real roots"],
      solution: [
        "Δ = 1² − 4(1)(1) = −3.",
        "Negative discriminant means no real square root, hence no real x.",
      ],
      conceptNoteIds: ["qf-and-roots"],
    },
    {
      id: "qf-pq-6",
      question:
        "The sum of a number and its reciprocal is 13/6. Find the number(s).",
      difficulty: "hard",
      style: "word-problem",
      hints: ["Let the number be x; then x + 1/x = 13/6", "Multiply by 6x"],
      expectedAnswer: "x = 3/2 or x = 2/3",
      acceptedAnswers: ["3/2 and 2/3", "x=1.5 or x=2/3"],
      solution: [
        "x + 1/x = 13/6 → multiply by 6x: 6x² + 6 = 13x.",
        "6x² − 13x + 6 = 0.",
        "Δ = 169 − 144 = 25.",
        "x = (13 ± 5) / 12 → x = 18/12 = 3/2 or x = 8/12 = 2/3.",
      ],
    },
    {
      id: "qf-pq-7",
      question: "Using the formula, solve 2x² − 5x + 2 = 0.",
      difficulty: "medium",
      style: "exam-style",
      hints: ["Δ = 25 − 16 = 9"],
      expectedAnswer: "x = 2 or x = 1/2",
      acceptedAnswers: ["x=2, x=1/2", "2 and 1/2"],
      solution: [
        "x = (5 ± 3) / 4.",
        "x = 8/4 = 2 or x = 2/4 = 1/2.",
      ],
    },
    {
      id: "qf-pq-8",
      question:
        "If one root of x² − kx + 6 = 0 is 2, find k using the formula or by substitution, then find the other root.",
      difficulty: "hard",
      style: "reasoning",
      hints: ["Substitute x = 2 into the equation", "Product of roots is 6"],
      expectedAnswer: "k = 5; other root = 3",
      acceptedAnswers: ["k=5, other root 3", "k = 5 and 3"],
      solution: [
        "2² − 2k + 6 = 0 → 10 − 2k = 0 → k = 5.",
        "Equation: x² − 5x + 6 = 0 → (x − 2)(x − 3) = 0.",
        "Other root is 3.",
      ],
    },
  ],
  difficulty: "medium",
  relatedTopicIds: [
    "standard-form-quadratic",
    "factorisation-quadratic",
    "discriminant",
    "zeros-and-coefficients",
  ],
  estimatedMinutes: 40,
};

const DISCRIMINANT: Topic = {
  id: "discriminant",
  chapterId: "quadratic-equations",
  title: "Nature of Roots (Discriminant)",
  shortDescription:
    "Use Δ = b² − 4ac to predict two distinct real roots, equal roots, or no real roots.",
  learningObjectives: [
    "Compute the discriminant reliably",
    "Classify the nature of roots from Δ",
    "Connect Δ to the graph meeting the x-axis",
  ],
  prerequisites: ["Standard form", "Quadratic formula"],
  conceptNotes: [
    {
      id: "delta-meaning",
      title: "What Δ measures",
      body: "Δ = b² − 4ac sits under the square root in the quadratic formula. Its sign tells you whether real roots exist and whether they are distinct — often without fully solving.",
    },
    {
      id: "delta-cases",
      title: "Three cases",
      body: "Δ > 0: two distinct real roots (parabola crosses the x-axis twice). Δ = 0: repeated real root (touches once). Δ < 0: no real roots (does not meet the x-axis). Class 10 focuses on real roots.",
    },
  ],
  keyPoints: [
    "Δ = b² − 4ac",
    "Δ > 0 → two distinct real roots",
    "Δ = 0 → equal real roots",
    "Δ < 0 → no real roots",
  ],
  formulas: [
    "Δ = b² − 4ac",
    "Δ > 0: two distinct real roots",
    "Δ = 0: two equal real roots",
    "Δ < 0: no real roots",
  ],
  examples: [
    {
      id: "disc-ex-1",
      title: "Equal roots",
      question: "Find the nature of roots of x² − 4x + 4 = 0.",
      steps: [
        "Δ = 16 − 16 = 0.",
        "Equal real roots.",
        "Root is x = 2 (repeated).",
      ],
      answer: "Equal real roots (both 2)",
      explanation: "Zero discriminant means the ± term vanishes, leaving one repeated value.",
    },
    {
      id: "disc-ex-2",
      title: "No real roots",
      question: "Nature of roots of x² + x + 1 = 0?",
      steps: ["Δ = 1 − 4 = −3 < 0.", "No real roots."],
      answer: "No real roots",
      explanation: "You cannot take a real square root of −3, so the formula yields no real x.",
    },
    {
      id: "disc-ex-3",
      title: "Find parameter for equal roots",
      question: "Find k so that kx² − 2x + 1 = 0 has equal roots (k ≠ 0).",
      steps: [
        "Δ = 4 − 4k(1) = 4 − 4k.",
        "Set Δ = 0 → k = 1.",
      ],
      answer: "k = 1",
      explanation: "Equal roots require Δ = 0. Solving for k gives the needed coefficient.",
    },
  ],
  commonMistakes: [
    "Thinking Δ < 0 means the equation has no solutions in any number system (complex roots exist, beyond Class 10 scope)",
    "Confusing Δ = 0 with ‘no roots’",
    "Forgetting to set Δ = 0 when a parameter is required for equal roots",
  ],
  hints: [
    "You can classify roots without fully solving",
    "Link Δ to whether the parabola crosses the x-axis",
  ],
  practiceQuestions: [
    {
      id: "disc-pq-1",
      question: "For 2x² − 3x + 5 = 0, find Δ and state the nature of roots.",
      difficulty: "easy",
      style: "direct",
      hints: ["Δ = b² − 4ac"],
      expectedAnswer: "Δ = -31; no real roots",
      acceptedAnswers: ["Δ=-31, no real roots", "discriminant -31"],
      solution: ["Δ = 9 − 40 = −31 < 0 → no real roots."],
    },
    {
      id: "disc-pq-2",
      question: "Find k so that kx² − 2x + 1 = 0 has equal roots (k ≠ 0).",
      difficulty: "medium",
      style: "multi-step",
      hints: ["Set Δ = 0"],
      expectedAnswer: "k = 1",
      acceptedAnswers: ["k=1"],
      solution: ["Δ = 4 − 4k = 0 → k = 1."],
    },
    {
      id: "disc-pq-3",
      question: "If Δ > 0 for a quadratic, how many times does its graph cross the x-axis?",
      difficulty: "easy",
      style: "conceptual",
      hints: ["Distinct real roots ↔ distinct intercepts"],
      expectedAnswer: "Twice",
      acceptedAnswers: ["2 times", "two times"],
      solution: ["Two distinct real roots mean two distinct x-intercepts."],
    },
    {
      id: "disc-pq-4",
      question: "For what values of m does x² − mx + 9 = 0 have real roots?",
      difficulty: "hard",
      style: "exam-style",
      hints: ["Need Δ ≥ 0"],
      expectedAnswer: "m ≤ -6 or m ≥ 6",
      acceptedAnswers: ["|m| ≥ 6", "m ≤ -6 or m ≥ 6"],
      solution: [
        "Δ = m² − 36 ≥ 0.",
        "m² ≥ 36 → m ≤ −6 or m ≥ 6.",
      ],
    },
    {
      id: "disc-pq-5",
      question:
        "True or false: If Δ = 0, the quadratic has no roots. Justify.",
      difficulty: "medium",
      style: "error-identification",
      hints: ["Δ = 0 is the repeated-root case"],
      expectedAnswer: "False; it has two equal real roots",
      acceptedAnswers: ["false - equal roots", "false, repeated root"],
      solution: [
        "Δ = 0 means the formula gives x = −b/(2a) twice.",
        "There is a real root of multiplicity two.",
      ],
    },
  ],
  difficulty: "medium",
  relatedTopicIds: ["quadratic-formula", "factorisation-quadratic"],
  estimatedMinutes: 25,
};

export const QUADRATIC_EQUATIONS_TOPICS: Topic[] = [
  STANDARD_FORM,
  FACTORISATION,
  QUADRATIC_FORMULA,
  DISCRIMINANT,
];
