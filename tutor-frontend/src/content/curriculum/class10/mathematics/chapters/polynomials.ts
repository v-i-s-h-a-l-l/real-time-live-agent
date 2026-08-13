import type { Chapter, Topic } from "@/domain/curriculum/types";

export const POLYNOMIALS_CHAPTER: Chapter = {
  id: "polynomials",
  subjectId: "mathematics",
  title: "Polynomials",
  description:
    "Zeros of polynomial graphs, their relationship with coefficients, and systematic polynomial division.",
  order: 2,
  topicIds: [
    "geometrical-meaning-of-zeros",
    "zeros-and-coefficients",
    "division-algorithm-polynomials",
  ],
};

export const POLYNOMIALS_TOPICS: Topic[] = [
  {
    id: "geometrical-meaning-of-zeros",
    chapterId: "polynomials",
    title: "Geometrical Meaning of Zeros",
    shortDescription:
      "Interpret a polynomial's zeros as the x-coordinates where its graph meets the x-axis.",
    learningObjectives: [
      "Connect p(a) = 0 with the point (a, 0) on a graph",
      "Read the number and values of zeros from graphical information",
      "Relate polynomial degree to the maximum possible number of zeros",
      "Distinguish crossing, touching, and no intersection with the x-axis",
    ],
    prerequisites: ["Cartesian coordinates", "Plotting ordered pairs", "Evaluating a polynomial"],
    conceptNotes: [
      {
        id: "gmz-zero-as-intercept",
        title: "A zero is an x-intercept",
        body:
          "On the graph y = p(x), a zero is an x-value a for which p(a) = 0. Therefore (a, 0) lies on the x-axis. Read the x-coordinate, not the y-coordinate. A graph may cross the axis or merely touch it; both give a zero.",
      },
      {
        id: "gmz-degree-and-zeros",
        title: "Degree limits the number of zeros",
        body:
          "A non-zero polynomial of degree n can have at most n distinct real zeros. A linear polynomial has one zero; a quadratic may have 0, 1, or 2; and a cubic may have 1, 2, or 3 distinct real zeros. Degree gives a maximum, not a guarantee.",
      },
      {
        id: "gmz-graph-behaviour",
        title: "Crossing and touching",
        body:
          "When a curve crosses the x-axis, the sign of p(x) changes around that zero. When it touches and turns back, the same zero is repeated and the sign need not change. At Class 10 level, both situations count as an x-intercept, though the graph shows only one distinct zero at that point.",
      },
    ],
    keyPoints: [
      "Zeros are x-coordinates of points where y = 0.",
      "The y-intercept p(0) is generally not a zero.",
      "A degree-n polynomial has at most n distinct zeros.",
      "Touching the x-axis also represents a zero.",
    ],
    formulas: [
      "p(a) = 0 ⇔ a is a zero of p(x)",
      "p(a) = 0 ⇔ (a, 0) lies on y = p(x)",
      "Number of distinct real zeros ≤ degree of a non-zero polynomial",
    ],
    examples: [
      {
        id: "gmz-ex-1",
        title: "Read zeros from intercepts",
        question:
          "The graph of y = p(x) crosses the x-axis at (-3, 0) and (2, 0), and crosses the y-axis at (0, -6). Find the zeros.",
        steps: [
          "Zeros occur where the graph has y-coordinate 0.",
          "The x-axis intersections have x-coordinates -3 and 2.",
          "The point (0, -6) is a y-intercept and does not represent a zero.",
        ],
        answer: "The zeros are -3 and 2.",
        explanation:
          "Only x-axis intersections matter when reading zeros of a polynomial.",
        commonMistake: "Including -6 because it appears at the y-intercept.",
      },
      {
        id: "gmz-ex-2",
        title: "Infer a graph from a factorised polynomial",
        question: "How many distinct x-axis intersections does y = (x - 1)²(x + 4) have?",
        steps: [
          "Set each factor equal to zero: x - 1 = 0 gives x = 1.",
          "The repeated factor (x - 1)² means the graph touches the axis at x = 1.",
          "x + 4 = 0 gives x = -4, where the graph crosses the axis.",
        ],
        answer: "There are 2 distinct x-axis intersections: x = 1 and x = -4.",
        explanation:
          "The polynomial has degree 3 counting multiplicity, but only two distinct zeros.",
      },
    ],
    commonMistakes: [
      "Reading y-coordinates instead of x-coordinates at intercepts.",
      "Assuming a degree-n polynomial must have exactly n real zeros.",
      "Ignoring a point where the graph touches but does not cross the x-axis.",
    ],
    hints: [
      "Trace the x-axis and record every x-coordinate where the graph meets it.",
      "Use degree only as an upper bound.",
      "Check a claimed zero a by evaluating p(a).",
    ],
    practiceQuestions: [
      {
        id: "gmz-pq-1",
        question: "The graph of p(x) meets the x-axis at (-2, 0), (0, 0), and (5, 0). State its zeros.",
        difficulty: "easy",
        style: "direct",
        hints: ["Take the x-coordinate of each x-axis point."],
        expectedAnswer: "-2, 0, and 5",
        acceptedAnswers: ["{-2, 0, 5}", "x = -2, 0, 5"],
        solution: ["Each listed point has y = 0.", "Therefore p(-2) = p(0) = p(5) = 0, so the zeros are -2, 0, and 5."],
        conceptNoteIds: ["gmz-zero-as-intercept"],
      },
      {
        id: "gmz-pq-2",
        question: "Can a quadratic polynomial have exactly one distinct real zero? Explain graphically.",
        difficulty: "easy",
        style: "conceptual",
        hints: ["Think of a parabola whose vertex lies on the x-axis."],
        expectedAnswer: "Yes. Its parabola can touch the x-axis at one point and turn back.",
        solution: [
          "A quadratic graph is a parabola.",
          "If its vertex lies on the x-axis, the graph touches the axis at only that point.",
          "Hence it has one distinct real zero (a repeated zero).",
        ],
        conceptNoteIds: ["gmz-graph-behaviour"],
      },
      {
        id: "gmz-pq-3",
        question:
          "A student says, 'A cubic polynomial always has three x-intercepts because its degree is 3.' Is the statement correct?",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Degree gives the maximum number, not necessarily the exact number."],
        expectedAnswer: "No. A cubic has at most three distinct real zeros and may have only one.",
        solution: [
          "The theorem says a degree-3 polynomial has at most 3 distinct real zeros.",
          "For example, p(x) = x³ + 1 has only the real zero x = -1.",
          "Thus the student's statement replaces 'at most' with 'always' and is false.",
        ],
        conceptNoteIds: ["gmz-degree-and-zeros"],
      },
      {
        id: "gmz-pq-4",
        question: "Without drawing, find the x-axis intersections of y = x² - 7x + 12.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["Factorise the polynomial."],
        expectedAnswer: "(3, 0) and (4, 0)",
        acceptedAnswers: ["x = 3 and x = 4", "3, 4"],
        solution: [
          "Factorise x² - 7x + 12 = (x - 3)(x - 4).",
          "Set y = 0: (x - 3)(x - 4) = 0.",
          "Thus x = 3 or x = 4, giving points (3, 0) and (4, 0).",
        ],
        conceptNoteIds: ["gmz-zero-as-intercept"],
      },
      {
        id: "gmz-pq-5",
        question:
          "A degree-4 polynomial graph touches the x-axis at x = -1 and crosses it at x = 2 and x = 5. What can you say about its distinct real zeros and why does this not contradict its degree?",
        difficulty: "hard",
        style: "reasoning",
        hints: ["Count distinct x-coordinates and remember that touching may represent a repeated zero."],
        expectedAnswer: "It has 3 distinct real zeros: -1, 2, and 5; degree 4 allows at most 4 and the touching zero may be repeated.",
        solution: [
          "Each meeting with the x-axis contributes a distinct zero, so the zeros are -1, 2, and 5.",
          "There are 3 distinct real zeros.",
          "A degree-4 polynomial may have fewer than 4 distinct real zeros; the touch at -1 is consistent with an even multiplicity.",
        ],
        conceptNoteIds: ["gmz-degree-and-zeros", "gmz-graph-behaviour"],
      },
    ],
    difficulty: "easy",
    relatedTopicIds: ["zeros-and-coefficients", "factorisation-quadratic"],
    estimatedMinutes: 35,
  },
  {
    id: "zeros-and-coefficients",
    chapterId: "polynomials",
    title: "Relationship Between Zeros and Coefficients",
    shortDescription:
      "Connect the zeros of quadratic and cubic polynomials to their coefficients and construct polynomials from zeros.",
    learningObjectives: [
      "Calculate the sum and product of zeros of a quadratic",
      "Verify coefficient relationships using known zeros",
      "Construct a polynomial when its zeros are given",
      "Apply the three zero-coefficient relationships for a cubic",
    ],
    prerequisites: ["Factorising quadratics", "Algebraic identities", "Geometrical meaning of zeros"],
    conceptNotes: [
      {
        id: "zac-quadratic-relations",
        title: "Quadratic zero-coefficient relations",
        body:
          "If α and β are zeros of ax² + bx + c, a ≠ 0, then α + β = -b/a and αβ = c/a. These follow by writing the polynomial as a(x - α)(x - β) and comparing coefficients.",
      },
      {
        id: "zac-form-polynomial",
        title: "Constructing a polynomial from zeros",
        body:
          "A monic quadratic with zeros α and β is (x - α)(x - β) = x² - (α + β)x + αβ. Any non-zero constant multiple has the same zeros, so unless a leading coefficient is specified, infinitely many polynomials are possible.",
      },
      {
        id: "zac-cubic-relations",
        title: "Relations for a cubic",
        body:
          "For ax³ + bx² + cx + d with zeros α, β, γ: α + β + γ = -b/a; αβ + βγ + γα = c/a; and αβγ = -d/a. Notice the alternating signs.",
      },
    ],
    keyPoints: [
      "For a quadratic, sum uses -b/a and product uses c/a.",
      "Always include the leading coefficient a in coefficient comparisons.",
      "Non-zero constant multiples of a polynomial have the same zeros.",
      "Cubic relations alternate signs: negative, positive, negative.",
    ],
    formulas: [
      "α + β = -b/a",
      "αβ = c/a",
      "p(x) = k[x² - (α + β)x + αβ], k ≠ 0",
      "α + β + γ = -b/a; αβ + βγ + γα = c/a; αβγ = -d/a",
    ],
    examples: [
      {
        id: "zac-ex-1",
        title: "Verify zeros and coefficients",
        question: "Find the zeros of 2x² - 7x + 3 and verify their sum and product.",
        steps: [
          "Factorise: 2x² - 7x + 3 = (2x - 1)(x - 3).",
          "The zeros are α = 1/2 and β = 3.",
          "Their sum is 1/2 + 3 = 7/2, equal to -b/a = -(-7)/2.",
          "Their product is (1/2)(3) = 3/2, equal to c/a = 3/2.",
        ],
        answer: "Zeros: 1/2 and 3; sum = 7/2 and product = 3/2.",
        explanation: "Both calculated values agree exactly with the coefficient formulas.",
        commonMistake: "Writing the sum as b/a = -7/2 instead of -b/a.",
      },
      {
        id: "zac-ex-2",
        title: "Build a polynomial from transformed zeros",
        question: "If α and β are zeros of x² - 5x + 6, form a monic polynomial whose zeros are α + 1 and β + 1.",
        steps: [
          "From the original polynomial, α + β = 5 and αβ = 6.",
          "New sum = (α + 1) + (β + 1) = 7.",
          "New product = (α + 1)(β + 1) = αβ + α + β + 1 = 12.",
          "The monic polynomial is x² - (new sum)x + new product.",
        ],
        answer: "x² - 7x + 12",
        explanation: "The new polynomial is constructed from the sum and product of the transformed zeros.",
      },
    ],
    commonMistakes: [
      "Forgetting the negative sign in the sum of zeros.",
      "Using c instead of c/a when the polynomial is not monic.",
      "Claiming there is only one polynomial with given zeros instead of allowing a non-zero multiplier.",
    ],
    hints: [
      "Label a, b, and c with their signs before substituting.",
      "When zeros are transformed, calculate their new sum and product first.",
      "Expand a(x - α)(x - β) to check your polynomial.",
    ],
    practiceQuestions: [
      {
        id: "zac-pq-1",
        question: "Find the sum and product of the zeros of 3x² + 5x - 2.",
        difficulty: "easy",
        style: "direct",
        hints: ["Here a = 3, b = 5, c = -2."],
        expectedAnswer: "Sum = -5/3; product = -2/3.",
        acceptedAnswers: ["-5/3, -2/3"],
        solution: ["α + β = -b/a = -5/3.", "αβ = c/a = -2/3."],
        conceptNoteIds: ["zac-quadratic-relations"],
      },
      {
        id: "zac-pq-2",
        question: "Form a monic quadratic polynomial whose zeros are -4 and 3.",
        difficulty: "easy",
        style: "direct",
        hints: ["Use (x - α)(x - β)."],
        expectedAnswer: "x² + x - 12",
        acceptedAnswers: ["p(x) = x² + x - 12", "x^2 + x - 12"],
        solution: [
          "The sum is -4 + 3 = -1 and the product is (-4)(3) = -12.",
          "p(x) = x² - (-1)x - 12 = x² + x - 12.",
        ],
        conceptNoteIds: ["zac-form-polynomial"],
      },
      {
        id: "zac-pq-3",
        question: "One zero of 2x² - 5x + k is 2. Find k and the other zero.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["Substitute x = 2 to find k, then use the sum of zeros."],
        expectedAnswer: "k = 2 and the other zero is 1/2.",
        solution: [
          "Since 2 is a zero, 2(2²) - 5(2) + k = 0.",
          "8 - 10 + k = 0, so k = 2.",
          "The sum of zeros is -b/a = 5/2.",
          "If the other zero is β, 2 + β = 5/2, so β = 1/2.",
        ],
        conceptNoteIds: ["zac-quadratic-relations"],
      },
      {
        id: "zac-pq-4",
        question:
          "A student forms x² - x - 6 for zeros 2 and -3. Identify the error and give the correct polynomial.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Calculate the sum 2 + (-3) carefully."],
        expectedAnswer: "The sum is -1, so the correct polynomial is x² + x - 6.",
        solution: [
          "The zeros have sum -1 and product -6.",
          "The polynomial is x² - (sum)x + product.",
          "Thus it is x² - (-1)x - 6 = x² + x - 6.",
        ],
        conceptNoteIds: ["zac-form-polynomial"],
      },
      {
        id: "zac-pq-5",
        question:
          "If α and β are zeros of 2x² - 6x + 5, form a polynomial whose zeros are 1/α and 1/β.",
        difficulty: "hard",
        style: "exam-style",
        hints: ["The new sum is (α + β)/(αβ), and the new product is 1/(αβ)."],
        expectedAnswer: "5x² - 6x + 2",
        acceptedAnswers: ["5x^2 - 6x + 2", "Any non-zero multiple of 5x² - 6x + 2"],
        solution: [
          "For the original zeros, α + β = 3 and αβ = 5/2.",
          "The reciprocal sum is (α + β)/(αβ) = 3/(5/2) = 6/5.",
          "The reciprocal product is 1/(αβ) = 2/5.",
          "A monic polynomial is x² - (6/5)x + 2/5; multiplying by 5 gives 5x² - 6x + 2.",
        ],
        conceptNoteIds: ["zac-quadratic-relations", "zac-form-polynomial"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: [
      "geometrical-meaning-of-zeros",
      "division-algorithm-polynomials",
      "factorisation-quadratic",
      "quadratic-formula",
    ],
    estimatedMinutes: 50,
  },
  {
    id: "division-algorithm-polynomials",
    chapterId: "polynomials",
    title: "Division Algorithm for Polynomials",
    shortDescription:
      "Divide polynomials, track quotient and remainder, and use the result to verify factors.",
    learningObjectives: [
      "State the polynomial division algorithm with its degree condition",
      "Perform polynomial long division accurately",
      "Verify a division result by multiplication",
      "Use a zero remainder to recognise polynomial factors",
    ],
    prerequisites: ["Polynomial degree", "Collecting like terms", "Algebraic multiplication"],
    conceptNotes: [
      {
        id: "dap-division-identity",
        title: "The division identity",
        body:
          "For polynomials f(x) and non-zero g(x), there are unique polynomials q(x) and r(x) such that f(x) = g(x)q(x) + r(x), where r(x) = 0 or degree r < degree g. This is the polynomial version of dividend = divisor × quotient + remainder.",
      },
      {
        id: "dap-long-division",
        title: "Polynomial long division",
        body:
          "Arrange all terms in descending powers, inserting zero coefficients for missing powers. Divide leading term by leading term, write that quotient term, multiply the whole divisor, subtract, and repeat until the remainder degree is smaller than the divisor degree.",
      },
      {
        id: "dap-factor-check",
        title: "Remainders and factors",
        body:
          "If division of f(x) by g(x) gives remainder zero, then g(x) is a factor of f(x). After any division, verify by expanding g(x)q(x) + r(x). A non-zero remainder is valid only if its degree is lower than that of g(x).",
      },
    ],
    keyPoints: [
      "Write missing terms with coefficient zero before dividing.",
      "Divide leading terms, then multiply and subtract the entire divisor.",
      "Stop only when the remainder has lower degree than the divisor.",
      "Check that divisor × quotient + remainder reproduces the dividend.",
    ],
    formulas: [
      "f(x) = g(x)q(x) + r(x), where r(x) = 0 or deg r < deg g",
      "Remainder 0 ⇔ g(x) is a factor of f(x)",
    ],
    examples: [
      {
        id: "dap-ex-1",
        title: "Long division with a missing term",
        question: "Divide 2x³ + 3x² - 5 by x + 2.",
        steps: [
          "Write the dividend as 2x³ + 3x² + 0x - 5.",
          "2x³ ÷ x = 2x². Subtract (2x³ + 4x²) to get -x² + 0x.",
          "-x² ÷ x = -x. Subtract (-x² - 2x) to get 2x - 5.",
          "2x ÷ x = 2. Subtract (2x + 4) to get remainder -9.",
        ],
        answer: "Quotient = 2x² - x + 2; remainder = -9.",
        explanation:
          "The remainder is constant, so its degree is less than the linear divisor's degree.",
        commonMistake: "Omitting the 0x placeholder and misaligning like powers.",
      },
      {
        id: "dap-ex-2",
        title: "Find an unknown from exact division",
        question: "If x² + kx - 12 is exactly divisible by x - 3, find k and the quotient.",
        steps: [
          "Exact divisibility means x - 3 is a factor, so substituting x = 3 gives zero.",
          "3² + 3k - 12 = 0, so 3k - 3 = 0 and k = 1.",
          "Then x² + x - 12 = (x - 3)(x + 4).",
        ],
        answer: "k = 1 and the quotient is x + 4.",
        explanation:
          "Zero remainder identifies the divisor as a factor; multiplication verifies the quotient.",
      },
    ],
    commonMistakes: [
      "Failing to insert zero terms for missing powers.",
      "Changing signs incorrectly when subtracting a multiplied divisor.",
      "Stopping while the remainder degree is still at least the divisor degree.",
    ],
    hints: [
      "Keep equal powers in vertical columns.",
      "Put brackets around the entire expression being subtracted.",
      "Finish with the identity dividend = divisor × quotient + remainder.",
    ],
    practiceQuestions: [
      {
        id: "dap-pq-1",
        question: "For f(x) = x³ - 4x + 3, verify whether x - 1 is a factor.",
        difficulty: "easy",
        style: "direct",
        hints: ["Evaluate f(1)."],
        expectedAnswer: "Yes; f(1) = 0, so x - 1 is a factor.",
        solution: ["f(1) = 1³ - 4(1) + 3 = 0.", "Therefore division by x - 1 has remainder zero, so x - 1 is a factor."],
        conceptNoteIds: ["dap-factor-check"],
      },
      {
        id: "dap-pq-2",
        question: "Divide x² + 5x + 6 by x + 2.",
        difficulty: "easy",
        style: "multi-step",
        hints: ["Begin with x² ÷ x = x."],
        expectedAnswer: "Quotient = x + 3; remainder = 0.",
        acceptedAnswers: ["x + 3", "quotient x + 3, remainder 0"],
        solution: [
          "x² ÷ x = x; subtract x(x + 2) = x² + 2x to get 3x + 6.",
          "3x ÷ x = 3; subtract 3(x + 2) = 3x + 6 to get 0.",
          "Thus the quotient is x + 3 and the remainder is zero.",
        ],
        conceptNoteIds: ["dap-long-division"],
      },
      {
        id: "dap-pq-3",
        question: "Divide 3x³ - x² + 2x + 5 by x² + 1.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["The quotient begins with 3x."],
        expectedAnswer: "Quotient = 3x - 1; remainder = -x + 6.",
        solution: [
          "3x³ ÷ x² = 3x. Subtract 3x(x² + 1) = 3x³ + 3x to get -x² - x + 5.",
          "-x² ÷ x² = -1. Subtract -(x² + 1) = -x² - 1 to get -x + 6.",
          "The remainder degree 1 is less than divisor degree 2.",
        ],
        conceptNoteIds: ["dap-long-division"],
      },
      {
        id: "dap-pq-4",
        question:
          "A student reports quotient x + 1 and remainder 2x + 3 when dividing by x² - 1. Is the result in valid final form?",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Compare the degrees of the remainder and divisor."],
        expectedAnswer: "Yes. The remainder has degree 1, which is less than the divisor's degree 2.",
        solution: [
          "The divisor x² - 1 has degree 2.",
          "The remainder 2x + 3 has degree 1.",
          "Since 1 < 2, the degree condition is satisfied; the form is valid, subject to the multiplication check.",
        ],
        conceptNoteIds: ["dap-division-identity"],
      },
      {
        id: "dap-pq-5",
        question:
          "Find a and b if 2x³ + ax² + bx - 6 is exactly divisible by x² - 1 and the quotient is 2x + 3.",
        difficulty: "hard",
        style: "reasoning",
        hints: ["Multiply the given divisor and quotient; exact division means no remainder."],
        expectedAnswer: "No values of a and b satisfy all the stated conditions.",
        solution: [
          "Exact division gives 2x³ + ax² + bx - 6 = (x² - 1)(2x + 3).",
          "Expand: (x² - 1)(2x + 3) = 2x³ + 3x² - 2x - 3.",
          "The constant term would be -3, not -6, so the stated conditions are inconsistent.",
          "Therefore no values of a and b satisfy all the conditions.",
        ],
        conceptNoteIds: ["dap-division-identity", "dap-factor-check"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["zeros-and-coefficients", "factorisation-quadratic"],
    estimatedMinutes: 50,
  },
];
