import type { Chapter, Topic } from "@/domain/curriculum/types";

export const LINEAR_EQUATIONS_CHAPTER: Chapter = {
  id: "pair-of-linear-equations",
  subjectId: "mathematics",
  title: "Pair of Linear Equations in Two Variables",
  description:
    "Graphical and algebraic solution methods, mathematical modelling, and consistency of two-variable linear systems.",
  order: 3,
  topicIds: [
    "graphical-method",
    "substitution-method",
    "elimination-method",
    "consistency-of-linear-systems",
  ],
};

export const LINEAR_EQUATIONS_TOPICS: Topic[] = [
  {
    id: "graphical-method",
    chapterId: "pair-of-linear-equations",
    title: "Graphical Method",
    shortDescription:
      "Plot two linear equations and interpret their common point or line as the solution set.",
    learningObjectives: [
      "Generate points satisfying a linear equation",
      "Draw two straight-line graphs using a suitable scale",
      "Read an approximate or exact solution from their intersection",
      "Interpret intersecting, parallel, and coincident lines",
    ],
    prerequisites: ["Cartesian plane", "Plotting ordered pairs", "Linear equations in two variables"],
    conceptNotes: [
      {
        id: "gm-equation-as-line",
        title: "Each equation represents a line",
        body:
          "Every solution of ax + by + c = 0 is a point on one straight line. To draw it, find at least two correct points, often by setting x = 0 and y = 0. A third point is useful as a plotting check.",
      },
      {
        id: "gm-common-solution",
        title: "Intersection means simultaneous solution",
        body:
          "A solution of a pair must satisfy both equations. Graphically it is therefore a point lying on both lines. Intersecting lines give one solution, distinct parallel lines give none, and the same coincident line gives infinitely many.",
      },
      {
        id: "gm-graph-accuracy",
        title: "Accuracy and verification",
        body:
          "Choose a scale that includes all points, label axes, and use a ruler. A graphical answer may be approximate. Substitute the read-off coordinates into both original equations to detect plotting or scale errors.",
      },
    ],
    keyPoints: [
      "Use at least two points to draw each line.",
      "The common solution is the intersection point's ordered pair (x, y).",
      "Parallel distinct lines have no common point.",
      "Graphical answers should be checked in both equations.",
    ],
    formulas: [
      "ax + by + c = 0 represents a straight line",
      "One intersection → one solution",
      "Parallel distinct lines → no solution; coincident lines → infinitely many solutions",
    ],
    examples: [
      {
        id: "gm-ex-1",
        title: "Plot and locate one solution",
        question: "Solve graphically: x + y = 5 and x - y = 1.",
        steps: [
          "For x + y = 5, plot (0, 5) and (5, 0).",
          "For x - y = 1, plot (1, 0) and (3, 2).",
          "Draw both straight lines; they intersect at (3, 2).",
          "Check: 3 + 2 = 5 and 3 - 2 = 1.",
        ],
        answer: "x = 3, y = 2.",
        explanation: "The point (3, 2) lies on both lines, so it satisfies both equations simultaneously.",
        commonMistake: "Writing the point as (2, 3) after swapping x- and y-coordinates.",
      },
      {
        id: "gm-ex-2",
        title: "Recognise parallel lines",
        question: "Describe the graphical solution of 2x + y = 4 and 4x + 2y = 10.",
        steps: [
          "Rewrite the second equation by dividing by 2: 2x + y = 5.",
          "The equations have the same x and y coefficients but different constants.",
          "Thus they represent distinct lines with the same slope.",
        ],
        answer: "The lines are parallel and there is no solution.",
        explanation: "No ordered pair can make 2x + y equal both 4 and 5.",
      },
    ],
    commonMistakes: [
      "Using two incorrect or identical points to draw a line.",
      "Reading the axes in reverse order.",
      "Assuming all pairs of lines intersect.",
    ],
    hints: [
      "Make a small x-y value table for each equation.",
      "Use easy values that avoid fractions when possible.",
      "Substitute the graph's intersection into both equations.",
    ],
    practiceQuestions: [
      {
        id: "gm-pq-1",
        question: "Give two points on the line 2x + y = 6.",
        difficulty: "easy",
        style: "direct",
        hints: ["Set x = 0, then set y = 0."],
        expectedAnswer: "For example, (0, 6) and (3, 0).",
        acceptedAnswers: ["(0,6), (3,0)", "(0, 6) and (3, 0)"],
        solution: ["If x = 0, y = 6, giving (0, 6).", "If y = 0, 2x = 6, so x = 3, giving (3, 0)."],
        conceptNoteIds: ["gm-equation-as-line"],
      },
      {
        id: "gm-pq-2",
        question: "The graphs of two equations intersect at (-2, 4). What is their solution?",
        difficulty: "easy",
        style: "conceptual",
        hints: ["The intersection is the point satisfying both equations."],
        expectedAnswer: "x = -2, y = 4.",
        acceptedAnswers: ["(-2, 4)"],
        solution: ["The common point is (-2, 4).", "Hence the simultaneous solution is x = -2 and y = 4."],
        conceptNoteIds: ["gm-common-solution"],
      },
      {
        id: "gm-pq-3",
        question: "Solve graphically: x + 2y = 6 and x - y = 0.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["The second line is x = y."],
        expectedAnswer: "x = 2, y = 2.",
        acceptedAnswers: ["(2, 2)"],
        solution: [
          "For x + 2y = 6, use points (6, 0) and (0, 3).",
          "For x - y = 0, use points (0, 0) and (2, 2).",
          "The lines intersect at (2, 2).",
          "Check: 2 + 2(2) = 6 and 2 - 2 = 0.",
        ],
        conceptNoteIds: ["gm-equation-as-line", "gm-common-solution"],
      },
      {
        id: "gm-pq-4",
        question:
          "A student plots x + y = 4 using only the point (2, 2) and draws a vertical line through it. Explain the error.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["How many points determine a unique straight line?"],
        expectedAnswer: "One point is insufficient; points such as (0, 4) and (4, 0) give the correct sloping line.",
        solution: [
          "Infinitely many lines pass through a single point.",
          "Choose a second solution, such as (0, 4) or (4, 0).",
          "The correct line through (0, 4), (2, 2), and (4, 0) is not vertical.",
        ],
        conceptNoteIds: ["gm-equation-as-line", "gm-graph-accuracy"],
      },
      {
        id: "gm-pq-5",
        question:
          "Tickets for a school show cost ₹50 for adults and ₹30 for students. In all, 10 tickets cost ₹380. Form two equations and state the graphical solution.",
        difficulty: "hard",
        style: "word-problem",
        hints: ["Let x be adult tickets and y be student tickets."],
        expectedAnswer: "x + y = 10, 50x + 30y = 380; x = 4 adults and y = 6 students.",
        solution: [
          "Let x and y be the numbers of adult and student tickets.",
          "Total tickets: x + y = 10. Total cost: 50x + 30y = 380.",
          "The first line includes (0,10) and (10,0); the second includes (1,11) and (4,6).",
          "Their relevant intersection is (4, 6), so 4 adult and 6 student tickets were sold.",
        ],
        conceptNoteIds: ["gm-common-solution"],
      },
    ],
    difficulty: "easy",
    relatedTopicIds: ["substitution-method", "consistency-of-linear-systems"],
    estimatedMinutes: 45,
  },
  {
    id: "substitution-method",
    chapterId: "pair-of-linear-equations",
    title: "Substitution Method",
    shortDescription:
      "Express one variable in terms of the other, substitute, solve, and verify the ordered pair.",
    learningObjectives: [
      "Choose an efficient variable to isolate",
      "Substitute an equivalent expression with correct brackets",
      "Back-substitute to obtain the second coordinate",
      "Translate simple word problems into equations",
    ],
    prerequisites: ["Linear equations in one variable", "Rearranging formulas", "Signed-number operations"],
    conceptNotes: [
      {
        id: "sub-isolate-replace",
        title: "Isolate and replace",
        body:
          "Rearrange one equation to write x in terms of y or y in terms of x. Replace that variable in the other equation with the entire expression. This produces one equation in one variable. Isolating a variable with coefficient 1 or -1 usually reduces arithmetic.",
      },
      {
        id: "sub-back-check",
        title: "Back-substitution and checking",
        body:
          "After solving for one variable, substitute its value into either original equation or the isolated form to find the other. The final ordered pair must satisfy both original equations; checking both protects against sign and rearrangement errors.",
      },
      {
        id: "sub-special-outcomes",
        title: "What identities and contradictions mean",
        body:
          "Substitution may remove both variables. A true identity such as 0 = 0 means the equations describe the same line and have infinitely many solutions. A false statement such as 0 = 5 means the lines are parallel and there is no solution.",
      },
    ],
    keyPoints: [
      "Isolate the variable with coefficient ±1 when convenient.",
      "Use brackets around the substituted expression.",
      "Back-substitute only after solving the one-variable equation.",
      "Verify the result in both original equations.",
    ],
    formulas: [
      "If x = expression in y, replace x by that expression in the other equation",
      "0 = 0 after substitution → infinitely many solutions",
      "0 = non-zero number after substitution → no solution",
    ],
    examples: [
      {
        id: "sub-ex-1",
        title: "Substitute an isolated variable",
        question: "Solve x + y = 7 and 2x - y = 2 by substitution.",
        steps: [
          "From x + y = 7, write y = 7 - x.",
          "Substitute into the second equation: 2x - (7 - x) = 2.",
          "Simplify: 3x - 7 = 2, so 3x = 9 and x = 3.",
          "Back-substitute: y = 7 - 3 = 4.",
          "Check: 3 + 4 = 7 and 2(3) - 4 = 2.",
        ],
        answer: "x = 3, y = 4.",
        explanation: "Substitution turns two equations in two variables into one equation in one variable.",
        commonMistake: "Expanding -(7 - x) as -7 - x instead of -7 + x.",
      },
      {
        id: "sub-ex-2",
        title: "Model an age problem",
        question:
          "A mother is 24 years older than her daughter. In 4 years, the mother will be three times the daughter's age. Find their present ages.",
        steps: [
          "Let the daughter's age be d and the mother's age be m.",
          "The equations are m = d + 24 and m + 4 = 3(d + 4).",
          "Substitute m = d + 24: d + 28 = 3d + 12.",
          "Thus 16 = 2d, so d = 8 and m = 32.",
        ],
        answer: "Daughter: 8 years; mother: 32 years.",
        explanation: "The future-age equation adds 4 to both present ages before applying the multiplier.",
      },
    ],
    commonMistakes: [
      "Substituting back into the same rearranged equation without using the second condition.",
      "Dropping brackets around a multi-term expression.",
      "Finding one variable and forgetting to find or verify the other.",
    ],
    hints: [
      "Scan for a coefficient of 1 or -1 before choosing what to isolate.",
      "Write the substitution in a separate line before simplifying.",
      "Use the simpler equation for back-substitution.",
    ],
    practiceQuestions: [
      {
        id: "sub-pq-1",
        question: "Solve y = 2x and x + y = 12.",
        difficulty: "easy",
        style: "direct",
        hints: ["Replace y by 2x in the second equation."],
        expectedAnswer: "x = 4, y = 8.",
        acceptedAnswers: ["(4, 8)"],
        solution: ["x + 2x = 12, so 3x = 12 and x = 4.", "Then y = 2(4) = 8."],
        conceptNoteIds: ["sub-isolate-replace"],
      },
      {
        id: "sub-pq-2",
        question: "Solve 3x + y = 11 and x - 2y = -1 by substitution.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["From the first equation, y = 11 - 3x."],
        expectedAnswer: "x = 3, y = 2.",
        acceptedAnswers: ["(3, 2)"],
        solution: [
          "Write y = 11 - 3x.",
          "Substitute: x - 2(11 - 3x) = -1.",
          "x - 22 + 6x = -1, so 7x = 21 and x = 3.",
          "Then y = 11 - 9 = 2.",
        ],
        conceptNoteIds: ["sub-isolate-replace", "sub-back-check"],
      },
      {
        id: "sub-pq-3",
        question:
          "After substituting one equation into another, all variables cancel and the result is 0 = 0. What does this mean?",
        difficulty: "medium",
        style: "conceptual",
        hints: ["A true statement means every point of one line also satisfies the other."],
        expectedAnswer: "The equations are equivalent and have infinitely many solutions.",
        solution: [
          "The result 0 = 0 is true for every permitted value.",
          "Therefore the equations represent the same line.",
          "Every point on that line satisfies both, so there are infinitely many solutions.",
        ],
        conceptNoteIds: ["sub-special-outcomes"],
      },
      {
        id: "sub-pq-4",
        question:
          "A student changes 2x - y = 5 into y = 5 - 2x. Identify and correct the rearrangement error.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Move 2x first, then multiply by -1."],
        expectedAnswer: "The correct form is y = 2x - 5.",
        solution: [
          "From 2x - y = 5, subtract 2x: -y = 5 - 2x.",
          "Multiply the entire equation by -1: y = -5 + 2x = 2x - 5.",
        ],
        conceptNoteIds: ["sub-isolate-replace"],
      },
      {
        id: "sub-pq-5",
        question:
          "The sum of the digits of a two-digit number is 11. Reversing the digits makes the number 27 less than the original. Find the number.",
        difficulty: "hard",
        style: "word-problem",
        hints: ["Let tens digit be x and units digit be y; the number is 10x + y."],
        expectedAnswer: "74",
        acceptedAnswers: ["The number is 74."],
        solution: [
          "Let x be the tens digit and y the units digit. Then x + y = 11.",
          "The reversal condition is 10y + x = 10x + y - 27.",
          "This simplifies to y = x - 3.",
          "Substitute into x + y = 11: x + x - 3 = 11, so x = 7 and y = 4.",
          "Therefore the number is 74.",
        ],
        conceptNoteIds: ["sub-isolate-replace"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["graphical-method", "elimination-method", "consistency-of-linear-systems"],
    estimatedMinutes: 45,
  },
  {
    id: "elimination-method",
    chapterId: "pair-of-linear-equations",
    title: "Elimination Method",
    shortDescription:
      "Scale and combine equations so one variable cancels, then solve and verify.",
    learningObjectives: [
      "Choose the easier variable to eliminate",
      "Multiply complete equations to create opposite or equal coefficients",
      "Add or subtract equations with correct signs",
      "Use elimination in exam-style and word problems",
    ],
    prerequisites: ["Linear equations in one variable", "Multiples and LCM", "Substitution method"],
    conceptNotes: [
      {
        id: "elim-equalise",
        title: "Equalising coefficients",
        body:
          "Choose x or y and make its coefficients equal in magnitude, often using their LCM. Multiply every term on each side of an equation by the chosen multiplier. If the target coefficients have opposite signs, add; if they have the same sign, subtract.",
      },
      {
        id: "elim-solve-recover",
        title: "Eliminate, solve, and recover",
        body:
          "Combining the equations removes one variable and leaves a one-variable equation. Solve it, substitute into either original equation to recover the other value, and verify in both originals.",
      },
      {
        id: "elim-fraction-strategy",
        title: "Keeping arithmetic manageable",
        body:
          "Clear fractions first when useful. Before multiplying both equations, check whether simple addition or subtraction already eliminates a variable. Careful vertical alignment of x-terms, y-terms, and constants reduces sign mistakes.",
      },
    ],
    keyPoints: [
      "Multiply every term, including the constant.",
      "Opposite signs cancel by addition; same signs cancel by subtraction.",
      "Use the smallest convenient multipliers.",
      "Substitute the first value to recover the second.",
    ],
    formulas: [
      "Multiply equation 1 by m and equation 2 by n so ma₁ = ±na₂ or mb₁ = ±nb₂",
      "Opposite equal coefficients: add equations",
      "Same equal coefficients: subtract equations",
    ],
    examples: [
      {
        id: "elim-ex-1",
        title: "Eliminate without scaling",
        question: "Solve 3x + 2y = 11 and x - 2y = 1.",
        steps: [
          "The y-coefficients are opposite, so add the equations.",
          "(3x + 2y) + (x - 2y) = 11 + 1 gives 4x = 12.",
          "Thus x = 3.",
          "Substitute into x - 2y = 1: 3 - 2y = 1, so y = 1.",
        ],
        answer: "x = 3, y = 1.",
        explanation: "Opposite y-coefficients cancel immediately when the equations are added.",
        commonMistake: "Subtracting the equations and doubling y instead of eliminating it.",
      },
      {
        id: "elim-ex-2",
        title: "Scale both equations",
        question: "Solve 2x + 3y = 13 and 3x + 2y = 12.",
        steps: [
          "Multiply the first equation by 3: 6x + 9y = 39.",
          "Multiply the second equation by 2: 6x + 4y = 24.",
          "Subtract the second result from the first: 5y = 15, so y = 3.",
          "Substitute into 3x + 2y = 12: 3x + 6 = 12, so x = 2.",
        ],
        answer: "x = 2, y = 3.",
        explanation: "LCM(2, 3) = 6 makes the x-coefficients equal with small multipliers.",
      },
    ],
    commonMistakes: [
      "Multiplying only variable terms but not the constant.",
      "Adding equal coefficients with the same sign instead of subtracting.",
      "Applying the subtraction sign to only one term of an equation.",
    ],
    hints: [
      "Circle the variable with the easiest coefficient LCM.",
      "Write scaled equations on new lines before combining.",
      "If subtracting, use brackets around the entire second equation.",
    ],
    practiceQuestions: [
      {
        id: "elim-pq-1",
        question: "Solve 2x + 3y = 12 and 2x - y = 4 by elimination.",
        difficulty: "easy",
        style: "direct",
        hints: ["Subtract the second equation from the first."],
        expectedAnswer: "x = 3, y = 2.",
        acceptedAnswers: ["(3, 2)"],
        solution: [
          "Subtract: (2x + 3y) - (2x - y) = 12 - 4, giving 4y = 8.",
          "Thus y = 2.",
          "Then 2x - 2 = 4, so x = 3.",
        ],
        conceptNoteIds: ["elim-solve-recover"],
      },
      {
        id: "elim-pq-2",
        question: "Solve 4x + 5y = 22 and 3x - 2y = 5.",
        difficulty: "medium",
        style: "multi-step",
        hints: ["Multiply the first equation by 2 and the second by 5 to eliminate y."],
        expectedAnswer: "x = 3, y = 2.",
        acceptedAnswers: ["(3, 2)"],
        solution: [
          "Multiply by 2: 8x + 10y = 44.",
          "Multiply the second by 5: 15x - 10y = 25.",
          "Add: 23x = 69, so x = 3.",
          "Then 12 + 5y = 22, so y = 2.",
        ],
        conceptNoteIds: ["elim-equalise", "elim-solve-recover"],
      },
      {
        id: "elim-pq-3",
        question:
          "To eliminate x from 2x + 3y = 7 and 4x - y = 5, a student doubles only 2x and writes 4x + 3y = 7. Correct the step.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["An equation remains equivalent only if every term is multiplied."],
        expectedAnswer: "The correctly doubled equation is 4x + 6y = 14.",
        solution: [
          "Multiply every term of 2x + 3y = 7 by 2.",
          "This gives 4x + 6y = 14.",
          "It can then be combined with 4x - y = 5 by subtraction.",
        ],
        conceptNoteIds: ["elim-equalise"],
      },
      {
        id: "elim-pq-4",
        question: "For what value of k do 3x + 2y = 7 and 6x + ky = 14 represent the same equation?",
        difficulty: "medium",
        style: "reasoning",
        hints: ["The second equation must be exactly twice the first."],
        expectedAnswer: "k = 4",
        acceptedAnswers: ["4"],
        solution: [
          "Doubling 3x + 2y = 7 gives 6x + 4y = 14.",
          "Compare with 6x + ky = 14.",
          "Therefore k = 4.",
        ],
        conceptNoteIds: ["elim-equalise"],
      },
      {
        id: "elim-pq-5",
        question:
          "A fraction becomes 1/3 when 1 is subtracted from its numerator and becomes 1/2 when 1 is added to its denominator. Find the fraction.",
        difficulty: "hard",
        style: "word-problem",
        hints: ["Let the numerator be x and denominator be y; cross-multiply both conditions."],
        expectedAnswer: "2/3",
        acceptedAnswers: ["The fraction is 2/3."],
        solution: [
          "(x - 1)/y = 1/3 gives 3x - y = 3.",
          "x/(y + 1) = 1/2 gives 2x - y = 1.",
          "Subtract the second equation from the first: x = 2.",
          "Then 4 - y = 1, so y = 3; these equations give 2/3.",
          "Checking reveals (2 - 1)/3 = 1/3 and 2/(3 + 1) = 1/2, so the fraction is 2/3.",
        ],
        conceptNoteIds: ["elim-solve-recover"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["substitution-method", "consistency-of-linear-systems"],
    estimatedMinutes: 50,
  },
  {
    id: "consistency-of-linear-systems",
    chapterId: "pair-of-linear-equations",
    title: "Consistency of Linear Systems",
    shortDescription:
      "Classify a pair as uniquely solvable, dependent, or inconsistent using coefficient ratios.",
    learningObjectives: [
      "Write both equations in standard form before comparison",
      "Apply the a₁/a₂, b₁/b₂, c₁/c₂ tests",
      "Connect coefficient ratios with line geometry",
      "Find parameter values that change the number of solutions",
    ],
    prerequisites: ["Graphical method", "Equivalent fractions", "Standard form of a linear equation"],
    conceptNotes: [
      {
        id: "con-three-cases",
        title: "Consistent and inconsistent systems",
        body:
          "A pair is consistent if it has at least one solution. Intersecting lines have one solution and are consistent-independent. Coincident lines have infinitely many solutions and are consistent-dependent. Distinct parallel lines have no solution and are inconsistent.",
      },
      {
        id: "con-ratio-test",
        title: "The coefficient-ratio test",
        body:
          "For a₁x + b₁y + c₁ = 0 and a₂x + b₂y + c₂ = 0: if a₁/a₂ ≠ b₁/b₂, there is one solution; if a₁/a₂ = b₁/b₂ ≠ c₁/c₂, there is no solution; if all three ratios are equal, there are infinitely many solutions.",
      },
      {
        id: "con-parameters",
        title: "Systems containing a parameter",
        body:
          "First put both equations in standard form and identify coefficients with signs. Impose the ratio condition for the requested case, solve for the parameter, and check that any inequality condition is also satisfied.",
      },
    ],
    keyPoints: [
      "Move every term to the same side before identifying a, b, and c.",
      "Unequal a-ratio and b-ratio means exactly one solution.",
      "Equal first two ratios require checking the constant ratio.",
      "No solution corresponds to distinct parallel lines.",
    ],
    formulas: [
      "a₁/a₂ ≠ b₁/b₂ → one solution",
      "a₁/a₂ = b₁/b₂ ≠ c₁/c₂ → no solution",
      "a₁/a₂ = b₁/b₂ = c₁/c₂ → infinitely many solutions",
    ],
    examples: [
      {
        id: "con-ex-1",
        title: "Classify an inconsistent pair",
        question: "Classify 2x + 3y = 5 and 4x + 6y = 11.",
        steps: [
          "Write standard forms: 2x + 3y - 5 = 0 and 4x + 6y - 11 = 0.",
          "Compute a₁/a₂ = 2/4 = 1/2 and b₁/b₂ = 3/6 = 1/2.",
          "But c₁/c₂ = (-5)/(-11) = 5/11, not 1/2.",
        ],
        answer: "No solution; the system is inconsistent.",
        explanation: "Equal x- and y-coefficient ratios but a different constant ratio describe parallel distinct lines.",
        commonMistake: "Using 5/11 without first noting that both standard-form constants are negative; the ratio happens to match here, but signs matter generally.",
      },
      {
        id: "con-ex-2",
        title: "Choose a parameter for infinitely many solutions",
        question: "Find k if 3x + 2y - 5 = 0 and 6x + 4y - k = 0 have infinitely many solutions.",
        steps: [
          "For infinitely many solutions, all coefficient ratios must be equal.",
          "3/6 = 2/4 = 1/2.",
          "Require (-5)/(-k) = 1/2, so 5/k = 1/2.",
          "Hence k = 10.",
        ],
        answer: "k = 10.",
        explanation: "With k = 10, the second equation is exactly twice the first.",
      },
    ],
    commonMistakes: [
      "Comparing constants before moving equations into the same standard form.",
      "Declaring no solution as soon as the first two ratios are equal.",
      "Forgetting that coincident lines are consistent because they have solutions.",
    ],
    hints: [
      "Create a coefficient row (a, b, c) for each equation.",
      "Compare the first two ratios before calculating the third.",
      "For parameter questions, translate the requested geometry into ratio conditions.",
    ],
    practiceQuestions: [
      {
        id: "con-pq-1",
        question: "Classify x + y = 2 and 2x + 2y = 4.",
        difficulty: "easy",
        style: "direct",
        hints: ["Check whether one complete equation is a multiple of the other."],
        expectedAnswer: "Infinitely many solutions; consistent dependent.",
        acceptedAnswers: ["infinitely many solutions", "coincident lines"],
        solution: [
          "The second equation is exactly 2 times the first.",
          "Thus both equations represent the same line.",
          "The pair is consistent-dependent with infinitely many solutions.",
        ],
        conceptNoteIds: ["con-three-cases"],
      },
      {
        id: "con-pq-2",
        question: "Determine the number of solutions of 3x - 2y = 7 and 6x - 4y = 9.",
        difficulty: "easy",
        style: "conceptual",
        hints: ["Compare 3/6, (-2)/(-4), and (-7)/(-9) after standardising."],
        expectedAnswer: "No solution.",
        acceptedAnswers: ["inconsistent", "parallel distinct lines"],
        solution: [
          "Standard forms are 3x - 2y - 7 = 0 and 6x - 4y - 9 = 0.",
          "a₁/a₂ = 1/2 and b₁/b₂ = 1/2, but c₁/c₂ = 7/9.",
          "Therefore the lines are parallel and distinct, so there is no solution.",
        ],
        conceptNoteIds: ["con-ratio-test"],
      },
      {
        id: "con-pq-3",
        question: "For what value of k do kx + 3y = 5 and 4x + 6y = 9 have no solution?",
        difficulty: "medium",
        style: "multi-step",
        hints: ["For no solution, require k/4 = 3/6 but not equal to the constant ratio."],
        expectedAnswer: "k = 2",
        acceptedAnswers: ["2"],
        solution: [
          "No solution requires k/4 = 3/6.",
          "Thus k/4 = 1/2, giving k = 2.",
          "The standard-form constant ratio is (-5)/(-9) = 5/9, which differs from 1/2.",
          "Hence k = 2 indeed gives no solution.",
        ],
        conceptNoteIds: ["con-ratio-test", "con-parameters"],
      },
      {
        id: "con-pq-4",
        question:
          "A student says that a system with infinitely many solutions is inconsistent because there is no single answer. Correct the statement.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Consistent means at least one solution, not exactly one."],
        expectedAnswer: "It is consistent-dependent because it has infinitely many solutions; only a system with no solution is inconsistent.",
        solution: [
          "Consistency requires at least one common solution.",
          "Coincident lines share every point on the line, so they have infinitely many solutions.",
          "Therefore they are consistent-dependent, not inconsistent.",
        ],
        conceptNoteIds: ["con-three-cases"],
      },
      {
        id: "con-pq-5",
        question:
          "Find all values of k for which (k - 1)x + 3y = 2 and 4x + (k + 2)y = 5 have a unique solution.",
        difficulty: "hard",
        style: "exam-style",
        hints: ["A unique solution requires (k - 1)/4 ≠ 3/(k + 2)."],
        expectedAnswer: "All real k except k = (-1 + √57)/2 and k = (-1 - √57)/2.",
        solution: [
          "A unique solution requires (k - 1)/4 ≠ 3/(k + 2).",
          "Equality occurs when (k - 1)(k + 2) = 12.",
          "Expand: k² + k - 2 = 12, so k² + k - 14 = 0.",
          "The discriminant is 1 + 56 = 57, so the quadratic formula gives k = (-1 ± √57)/2.",
          "Therefore the unique-solution values are all real k except (-1 + √57)/2 and (-1 - √57)/2.",
        ],
        conceptNoteIds: ["con-ratio-test", "con-parameters"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["graphical-method", "substitution-method", "elimination-method"],
    estimatedMinutes: 45,
  },
];
