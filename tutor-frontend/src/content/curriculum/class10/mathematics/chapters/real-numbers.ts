import type { Chapter, Topic } from "@/domain/curriculum/types";

export const REAL_NUMBERS_CHAPTER: Chapter = {
  id: "real-numbers",
  subjectId: "mathematics",
  title: "Real Numbers",
  description:
    "Euclid's algorithm, unique prime factorisation, and rigorous reasoning about irrational numbers.",
  order: 1,
  topicIds: [
    "euclids-division-lemma",
    "fundamental-theorem-of-arithmetic",
    "irrational-numbers",
  ],
};

export const REAL_NUMBERS_TOPICS: Topic[] = [
  {
    id: "euclids-division-lemma",
    chapterId: "real-numbers",
    title: "Euclid's Division Lemma",
    shortDescription:
      "Represent integer division precisely and repeatedly apply it to calculate the HCF.",
    learningObjectives: [
      "Write positive integers in the form a = bq + r with the correct remainder restriction",
      "Use Euclid's algorithm to calculate the HCF of two positive integers",
      "Explain why the last non-zero remainder is the HCF",
      "Apply HCF reasoning to grouping and measurement problems",
    ],
    prerequisites: ["Whole-number division", "Factors and multiples", "Remainders"],
    conceptNotes: [
      {
        id: "edl-division-form",
        title: "Dividend, divisor, quotient, and remainder",
        body:
          "For positive integers a and b, with a > b, there are unique whole numbers q and r such that a = bq + r and 0 ≤ r < b. Here a is the dividend, b the divisor, q the quotient, and r the remainder. The strict condition r < b makes the representation unique.",
      },
      {
        id: "edl-hcf-algorithm",
        title: "Euclid's algorithm for HCF",
        body:
          "Divide the larger number by the smaller. Then divide the previous divisor by the non-zero remainder. Continue until the remainder becomes zero. The last non-zero remainder is the HCF because replacing a pair (a, b) by (b, r), where a = bq + r, does not change their common divisors.",
      },
      {
        id: "edl-applications",
        title: "Recognising HCF applications",
        body:
          "Use HCF when a problem asks for the greatest possible equal length, the largest identical group, or the biggest unit that measures several quantities exactly. The required unit must divide every given quantity, and 'greatest' selects their HCF.",
      },
    ],
    keyPoints: [
      "The remainder must satisfy 0 ≤ r < divisor.",
      "Each step of Euclid's algorithm uses the previous divisor and remainder.",
      "The last non-zero remainder, not the final zero, is the HCF.",
      "A zero remainder means the current divisor divides exactly.",
    ],
    formulas: [
      "a = bq + r, where 0 ≤ r < b",
      "If a = bq + r, then HCF(a, b) = HCF(b, r)",
    ],
    examples: [
      {
        id: "edl-ex-1",
        title: "Find an HCF by Euclid's algorithm",
        question: "Use Euclid's division algorithm to find HCF(867, 255).",
        steps: [
          "Divide 867 by 255: 867 = 255 × 3 + 102.",
          "Divide 255 by 102: 255 = 102 × 2 + 51.",
          "Divide 102 by 51: 102 = 51 × 2 + 0.",
          "The last non-zero remainder is 51.",
        ],
        answer: "HCF(867, 255) = 51.",
        explanation:
          "Common divisors are preserved at every division step, so the final non-zero remainder is the greatest common divisor.",
        commonMistake: "Reporting 0 as the HCF because it is the last remainder.",
      },
      {
        id: "edl-ex-2",
        title: "Largest square tile",
        question:
          "A rectangular floor is 135 cm by 225 cm. Find the side of the largest square tile that covers it without cutting.",
        steps: [
          "The tile side must divide both 135 and 225, so find their HCF.",
          "225 = 135 × 1 + 90.",
          "135 = 90 × 1 + 45.",
          "90 = 45 × 2 + 0.",
        ],
        answer: "The largest tile has side 45 cm.",
        explanation:
          "The greatest length that measures both dimensions exactly is their HCF.",
      },
    ],
    commonMistakes: [
      "Allowing a remainder equal to or larger than the divisor.",
      "Changing the order incorrectly instead of using the previous divisor as the next dividend.",
      "Stopping at the first remainder rather than continuing until remainder zero.",
    ],
    hints: [
      "At every line, check: dividend = divisor × quotient + remainder.",
      "For a word problem, underline words such as greatest, largest, and exactly.",
      "A quick multiplication check catches most quotient errors.",
    ],
    practiceQuestions: [
      {
        id: "edl-pq-1",
        question: "Express 455 in the form 42q + r, where 0 ≤ r < 42.",
        difficulty: "easy",
        style: "direct",
        hints: ["Find the largest multiple of 42 not exceeding 455."],
        expectedAnswer: "455 = 42 × 10 + 35; q = 10, r = 35.",
        acceptedAnswers: ["q = 10, r = 35", "10, 35"],
        solution: [
          "42 × 10 = 420 and 42 × 11 = 462 > 455.",
          "The remainder is 455 - 420 = 35.",
          "Thus 455 = 42 × 10 + 35, with 0 ≤ 35 < 42.",
        ],
        conceptNoteIds: ["edl-division-form"],
      },
      {
        id: "edl-pq-2",
        question: "Use Euclid's algorithm to find HCF(135, 225).",
        difficulty: "easy",
        style: "multi-step",
        hints: ["Begin by dividing 225 by 135."],
        expectedAnswer: "45",
        acceptedAnswers: ["HCF = 45", "HCF(135, 225) = 45"],
        solution: [
          "225 = 135 × 1 + 90.",
          "135 = 90 × 1 + 45.",
          "90 = 45 × 2 + 0.",
          "Therefore, HCF(135, 225) = 45.",
        ],
        conceptNoteIds: ["edl-hcf-algorithm"],
      },
      {
        id: "edl-pq-3",
        question:
          "A student writes 67 = 8 × 7 + 11 as an application of Euclid's lemma with divisor 8. Identify and correct the error.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Compare the claimed remainder with the divisor."],
        expectedAnswer: "The remainder 11 is invalid; 67 = 8 × 8 + 3.",
        solution: [
          "A valid remainder for divisor 8 must be less than 8.",
          "Since 11 ≥ 8, increase the quotient by 1 and subtract 8 from the remainder.",
          "Therefore 67 = 8 × 8 + 3.",
        ],
        conceptNoteIds: ["edl-division-form"],
      },
      {
        id: "edl-pq-4",
        question:
          "Find the greatest number that divides 245 and 1029 leaving remainder 5 in each case.",
        difficulty: "medium",
        style: "reasoning",
        hints: ["Subtract the common remainder before finding the HCF."],
        expectedAnswer: "16",
        acceptedAnswers: ["The greatest number is 16."],
        solution: [
          "If the divisor leaves remainder 5, it divides 245 - 5 = 240 and 1029 - 5 = 1024.",
          "1024 = 240 × 4 + 64.",
          "240 = 64 × 3 + 48; 64 = 48 × 1 + 16; 48 = 16 × 3.",
          "Hence HCF(240, 1024) = 16.",
        ],
        conceptNoteIds: ["edl-hcf-algorithm"],
      },
      {
        id: "edl-pq-5",
        question:
          "Three ribbons of lengths 96 cm, 144 cm, and 168 cm are cut into equal pieces of greatest possible length. Find the piece length and total number of pieces.",
        difficulty: "hard",
        style: "word-problem",
        hints: ["First find HCF(96, 144, 168), then divide each length by it."],
        expectedAnswer: "Each piece is 24 cm long, and there are 17 pieces.",
        solution: [
          "HCF(96, 144) = 48.",
          "HCF(48, 168) = 24, so the greatest equal length is 24 cm.",
          "Numbers of pieces are 96/24 = 4, 144/24 = 6, and 168/24 = 7.",
          "Total pieces = 4 + 6 + 7 = 17.",
        ],
        conceptNoteIds: ["edl-applications"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["fundamental-theorem-of-arithmetic"],
    estimatedMinutes: 40,
  },
  {
    id: "fundamental-theorem-of-arithmetic",
    chapterId: "real-numbers",
    title: "Fundamental Theorem of Arithmetic",
    shortDescription:
      "Use unique prime factorisation to reason about divisibility, HCF, LCM, and decimal expansions.",
    learningObjectives: [
      "State and apply the uniqueness of prime factorisation",
      "Calculate HCF and LCM from prime powers",
      "Use HCF × LCM = product for two positive integers",
      "Determine whether a rational number has a terminating decimal expansion",
    ],
    prerequisites: ["Prime and composite numbers", "Exponents", "Fractions in lowest terms"],
    conceptNotes: [
      {
        id: "fta-unique-factorisation",
        title: "Unique prime factorisation",
        body:
          "Every composite number can be expressed as a product of primes, and apart from the order of factors this representation is unique. For example, 360 = 2³ × 3² × 5. The number 1 is neither prime nor composite and is excluded from the theorem.",
      },
      {
        id: "fta-hcf-lcm",
        title: "Prime powers in HCF and LCM",
        body:
          "Write every number using the same list of relevant primes. The HCF takes the least exponent of each common prime; the LCM takes the greatest exponent of every prime present. For two positive integers a and b, HCF(a,b) × LCM(a,b) = ab.",
      },
      {
        id: "fta-decimal-expansion",
        title: "Terminating decimal criterion",
        body:
          "First reduce p/q to lowest terms. Its decimal expansion terminates exactly when q = 2^m × 5^n for non-negative integers m and n. Any other prime factor in the reduced denominator makes the decimal expansion non-terminating recurring.",
      },
    ],
    keyPoints: [
      "Prime factorisation is unique except for the order of factors.",
      "Use minimum exponents for HCF and maximum exponents for LCM.",
      "Reduce a fraction before testing its denominator.",
      "Only the prime factors 2 and 5 are allowed in a terminating decimal's reduced denominator.",
    ],
    formulas: [
      "HCF(a, b) × LCM(a, b) = a × b",
      "Terminating decimal ⇔ reduced denominator q = 2^m × 5^n",
    ],
    examples: [
      {
        id: "fta-ex-1",
        title: "HCF and LCM from prime factors",
        question: "Find the HCF and LCM of 144 and 180.",
        steps: [
          "Prime factorise: 144 = 2⁴ × 3².",
          "Prime factorise: 180 = 2² × 3² × 5.",
          "HCF uses minimum powers: 2² × 3² = 36.",
          "LCM uses maximum powers: 2⁴ × 3² × 5 = 720.",
        ],
        answer: "HCF = 36 and LCM = 720.",
        explanation:
          "The HCF contains only factors shared by both numbers; the LCM contains enough prime factors to be divisible by both.",
        commonMistake: "Taking the largest exponents for the HCF.",
      },
      {
        id: "fta-ex-2",
        title: "Test a decimal expansion",
        question: "Without long division, decide whether 77/210 has a terminating decimal expansion.",
        steps: [
          "Reduce the fraction: 77/210 = 11/30 because the common factor is 7.",
          "Factor the reduced denominator: 30 = 2 × 3 × 5.",
          "The denominator contains the prime factor 3 in addition to 2 and 5.",
        ],
        answer: "It is non-terminating recurring.",
        explanation:
          "A reduced rational number terminates only when its denominator has no prime factors other than 2 and 5.",
      },
    ],
    commonMistakes: [
      "Treating 1 as a prime number.",
      "Testing the denominator before reducing the fraction.",
      "Confusing the minimum-exponent HCF rule with the maximum-exponent LCM rule.",
    ],
    hints: [
      "Use a factor tree until every leaf is prime.",
      "For decimal questions, write 'reduce first' before doing anything else.",
      "Check HCF and LCM by multiplying them and comparing with the product of the two numbers.",
    ],
    practiceQuestions: [
      {
        id: "fta-pq-1",
        question: "Write 756 as a product of prime powers.",
        difficulty: "easy",
        style: "direct",
        hints: ["Repeatedly divide by 2, then 3."],
        expectedAnswer: "756 = 2² × 3³ × 7.",
        acceptedAnswers: ["2^2 × 3^3 × 7", "2² × 3³ × 7"],
        solution: [
          "756 = 2 × 378 = 2² × 189.",
          "189 = 3 × 63 = 3³ × 7.",
          "Thus 756 = 2² × 3³ × 7.",
        ],
        conceptNoteIds: ["fta-unique-factorisation"],
      },
      {
        id: "fta-pq-2",
        question: "Find the HCF and LCM of 72 and 120 using prime factorisation.",
        difficulty: "easy",
        style: "multi-step",
        hints: ["72 = 2³ × 3² and 120 = 2³ × 3 × 5."],
        expectedAnswer: "HCF = 24; LCM = 360.",
        solution: [
          "Use minimum exponents for HCF: 2³ × 3 = 24.",
          "Use maximum exponents for LCM: 2³ × 3² × 5 = 360.",
          "Check: 24 × 360 = 72 × 120 = 8640.",
        ],
        conceptNoteIds: ["fta-hcf-lcm"],
      },
      {
        id: "fta-pq-3",
        question:
          "The HCF of two numbers is 12, their LCM is 420, and one number is 60. Find the other number.",
        difficulty: "medium",
        style: "reasoning",
        hints: ["Use HCF × LCM = product of the numbers."],
        expectedAnswer: "84",
        acceptedAnswers: ["The other number is 84."],
        solution: [
          "Let the other number be n.",
          "12 × 420 = 60 × n.",
          "n = (12 × 420)/60 = 84.",
        ],
        conceptNoteIds: ["fta-hcf-lcm"],
      },
      {
        id: "fta-pq-4",
        question: "Does 13/3125 have a terminating decimal? If yes, state the number of decimal places.",
        difficulty: "medium",
        style: "conceptual",
        hints: ["Factor 3125 as a power of 5, then make the denominator a power of 10."],
        expectedAnswer: "Yes. It terminates after 5 decimal places: 13/3125 = 0.00416.",
        acceptedAnswers: ["Yes, 5 decimal places", "0.00416"],
        solution: [
          "3125 = 5⁵, so the denominator contains only the allowed prime 5.",
          "Multiply numerator and denominator by 2⁵ = 32.",
          "13/3125 = 416/100000 = 0.00416, which has 5 decimal places.",
        ],
        conceptNoteIds: ["fta-decimal-expansion"],
      },
      {
        id: "fta-pq-5",
        question:
          "Show that the square of any odd positive integer is of the form 8m + 1 for some integer m.",
        difficulty: "hard",
        style: "exam-style",
        hints: ["Write an odd integer as 2k + 1 and consider whether k is odd or even."],
        expectedAnswer: "For every odd n, n² = 8m + 1 for an integer m.",
        solution: [
          "Let n = 2k + 1. Then n² = 4k(k + 1) + 1.",
          "The consecutive integers k and k + 1 have an even product, so k(k + 1) = 2m for some integer m.",
          "Therefore n² = 4(2m) + 1 = 8m + 1.",
        ],
        conceptNoteIds: ["fta-unique-factorisation"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["euclids-division-lemma", "irrational-numbers"],
    estimatedMinutes: 50,
  },
  {
    id: "irrational-numbers",
    chapterId: "real-numbers",
    title: "Irrational Numbers",
    shortDescription:
      "Classify real numbers and construct contradiction proofs for irrational roots and related expressions.",
    learningObjectives: [
      "Distinguish rational numbers from irrational numbers",
      "Prove that √p is irrational when p is prime",
      "Use rational-number closure properties to prove related expressions irrational",
      "Identify flaws in informal irrationality arguments",
    ],
    prerequisites: ["Prime factorisation", "Fractions in lowest terms", "Proof by contradiction"],
    conceptNotes: [
      {
        id: "irr-rational-vs-irrational",
        title: "Rational and irrational numbers",
        body:
          "A number is rational if it can be written as p/q for integers p and q with q ≠ 0. Rational decimals terminate or recur. Irrational numbers cannot be written in that form and have non-terminating, non-recurring decimal expansions. A square root of a perfect square is rational; roots of non-square positive integers are irrational.",
      },
      {
        id: "irr-contradiction-proof",
        title: "The contradiction proof pattern",
        body:
          "To prove √p irrational, assume √p = a/b where a and b are coprime. Squaring gives a² = pb², so p divides a² and hence p divides a. Writing a = pk then forces p to divide b. This contradicts the assumption that a/b was in lowest terms.",
      },
      {
        id: "irr-closure-reasoning",
        title: "Reasoning with rational operations",
        body:
          "Rational numbers are closed under addition, subtraction, multiplication, and division by a non-zero rational. Therefore, if an expression involving a known irrational number were rational, rearranging it to make the irrational number equal to a rational expression creates a contradiction.",
      },
    ],
    keyPoints: [
      "A non-terminating recurring decimal is rational, not irrational.",
      "Always assume p/q is in lowest terms in a contradiction proof.",
      "For a prime p, p dividing a² implies p divides a.",
      "The sum of two irrational numbers is not always irrational.",
    ],
    formulas: [
      "Rational number = p/q, where p, q ∈ ℤ and q ≠ 0",
      "If p is prime and p | a², then p | a",
      "√n is irrational when n is a positive integer that is not a perfect square",
    ],
    examples: [
      {
        id: "irr-ex-1",
        title: "Prove √5 is irrational",
        question: "Prove by contradiction that √5 is irrational.",
        steps: [
          "Assume √5 = a/b, where a and b are coprime integers and b ≠ 0.",
          "Square both sides: a² = 5b². Hence 5 divides a², so 5 divides a.",
          "Write a = 5k. Substitution gives 25k² = 5b², so b² = 5k².",
          "Thus 5 also divides b, contradicting that a and b are coprime.",
        ],
        answer: "Therefore √5 is irrational.",
        explanation:
          "The rational assumption forces numerator and denominator to share factor 5, so no lowest-terms fraction can represent √5.",
        commonMistake: "Saying '5 divides a², therefore a is even'; the correct conclusion is that 5 divides a.",
      },
      {
        id: "irr-ex-2",
        title: "An irrational linear expression",
        question: "Show that 3 + 2√2 is irrational.",
        steps: [
          "Assume 3 + 2√2 is rational; call it r.",
          "Then 2√2 = r - 3, which is rational because r and 3 are rational.",
          "Dividing by non-zero rational 2 gives √2 = (r - 3)/2, a rational number.",
          "This contradicts the known irrationality of √2.",
        ],
        answer: "3 + 2√2 is irrational.",
        explanation:
          "Rearranging the assumed rational expression would make a known irrational number rational.",
      },
    ],
    commonMistakes: [
      "Calling every non-terminating decimal irrational without checking whether it recurs.",
      "Forgetting to specify that numerator and denominator are coprime.",
      "Assuming sums or products of irrational numbers are always irrational.",
    ],
    hints: [
      "In a proof, clearly state the assumption that will be contradicted.",
      "Try rearranging a compound expression until a known irrational number is isolated.",
      "Test general claims with pairs such as √2 and -√2.",
    ],
    practiceQuestions: [
      {
        id: "irr-pq-1",
        question: "Classify 0.272727... and √11 as rational or irrational.",
        difficulty: "easy",
        style: "conceptual",
        hints: ["A recurring decimal can be written as a fraction."],
        expectedAnswer: "0.272727... is rational; √11 is irrational.",
        solution: [
          "0.272727... repeats the block 27, so it is a recurring decimal and is rational.",
          "11 is not a perfect square, so √11 is irrational.",
        ],
        conceptNoteIds: ["irr-rational-vs-irrational"],
      },
      {
        id: "irr-pq-2",
        question: "Give two irrational numbers whose sum is rational.",
        difficulty: "easy",
        style: "reasoning",
        hints: ["Consider an irrational number and its additive inverse."],
        expectedAnswer: "For example, √2 and -√2; their sum is 0.",
        acceptedAnswers: ["√2 and -√2", "sqrt(2) and -sqrt(2)"],
        solution: [
          "Both √2 and -√2 are irrational.",
          "Their sum is √2 + (-√2) = 0, which is rational.",
        ],
        conceptNoteIds: ["irr-closure-reasoning"],
      },
      {
        id: "irr-pq-3",
        question: "Prove that √3 is irrational.",
        difficulty: "medium",
        style: "exam-style",
        hints: ["Assume √3 = a/b in lowest terms and square."],
        expectedAnswer: "√3 is irrational by contradiction.",
        solution: [
          "Assume √3 = a/b with HCF(a,b) = 1.",
          "Then a² = 3b², so 3 divides a; write a = 3k.",
          "Substitution gives 9k² = 3b², hence b² = 3k², so 3 divides b.",
          "Then 3 divides both a and b, contradicting HCF(a,b) = 1. Therefore √3 is irrational.",
        ],
        conceptNoteIds: ["irr-contradiction-proof"],
      },
      {
        id: "irr-pq-4",
        question:
          "A student argues: '√2 and √8 are irrational, so √2 × √8 must be irrational.' Find the error.",
        difficulty: "medium",
        style: "error-identification",
        hints: ["Calculate the product exactly."],
        expectedAnswer: "The product is √16 = 4, which is rational; products of irrational numbers need not be irrational.",
        solution: [
          "Compute √2 × √8 = √16 = 4.",
          "The result 4 is rational.",
          "Therefore the false step is assuming closure: irrational numbers are not closed under multiplication.",
        ],
        conceptNoteIds: ["irr-closure-reasoning"],
      },
      {
        id: "irr-pq-5",
        question: "Prove that 1/(2 + √3) is irrational.",
        difficulty: "hard",
        style: "multi-step",
        hints: ["Rationalise the denominator, then use a contradiction."],
        expectedAnswer: "1/(2 + √3) = 2 - √3, which is irrational.",
        solution: [
          "Rationalise: 1/(2 + √3) = (2 - √3)/((2 + √3)(2 - √3)).",
          "The denominator is 4 - 3 = 1, so the expression equals 2 - √3.",
          "If 2 - √3 were rational, then √3 would equal 2 minus a rational number and would be rational.",
          "This contradicts the irrationality of √3; hence the expression is irrational.",
        ],
        conceptNoteIds: ["irr-closure-reasoning"],
      },
    ],
    difficulty: "medium",
    relatedTopicIds: ["fundamental-theorem-of-arithmetic"],
    estimatedMinutes: 45,
  },
];
