"""Manual listening aid: prints what Cartesia will actually be given."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.speak_math import speak_for_tts  # noqa: E402

SAMPLES = [
    r"The zeros of a quadratic \(ax^{2}+bx+c\) satisfy \( \text{sum} = -\frac{b}{a}\)"
    r" and \( \text{product} = \frac{c}{a}\); similarly, for a cubic"
    r" \(ax^{3}+bx^{2}+cx+d\) the sum, sum-of-pairwise products, and product of its"
    r" three zeros relate to \(-\frac{b}{a},\;\frac{c}{a},\;-\frac{d}{a}\) respectively.",
    "On this slide we see that if \u03b1 and \u03b2 are the zeros of the quadratic"
    " a x\u00b2 + b x + c (with a \u2260 0), then their sum is \u03b1 + \u03b2 = \u2011b\u2044a"
    " and their product is \u03b1\u03b2 = c\u2044a. These formulas come from writing the"
    " polynomial as a(x \u2011 \u03b1)(x \u2011 \u03b2) and matching the coefficients.",
    "First, write the quadratic in the form a(x \u2212 \u03b1)(x \u2212 \u03b2) and compare"
    " it with 3x\u00b2 + 5x \u2212 2; what does that tell you about \u03b1 + \u03b2?",
    "Here is the rule.\n$\u03b1 + \u03b2 = -b/a$\n$\u03b1\u03b2 = c/a$\nTry it now.",
    "Factorise $(a+b)(a-b)$ and check the middle terms cancel.",
    "We expand $2(x+3)$ first, then use $x = (-b \\pm \\sqrt{b^2 - 4ac})/(2a)$.",
    "Euclid's Division Lemma: $a = bq + r, 0 \\leq r < b$.",
    "Sure, let's look at an example - it will help. The cost was 40-50 rupees.",
    "Take $x_1$ and $x_2$, then $x_1 + x_2 = 7$ and $x_1 x_2 = 12$.",
]

if __name__ == "__main__":
    for sample in SAMPLES:
        print("IN :", sample.replace("\n", " / "))
        print("OUT:", speak_for_tts(sample))
        print()
