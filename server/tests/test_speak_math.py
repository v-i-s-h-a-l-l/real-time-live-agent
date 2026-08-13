"""Spoken math for TTS — equations, fractions, roots, inequalities."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.speak_math import speak_for_tts, speak_math_expr  # noqa: E402


def test_equation_a_equals_bq_plus_r():
    spoken = speak_math_expr("a = bq + r")
    assert "equals" in spoken
    assert "times" in spoken
    assert "plus" in spoken
    assert "bq" not in spoken
    low = spoken.lower()
    assert "ay equals" in low
    assert "cue" in low
    assert "bee" in low
    assert "are" in low


def test_inequality_remainder_range():
    spoken = speak_math_expr(r"0 \leq r < b")
    assert "<" not in spoken
    assert "≤" not in spoken
    assert "greater than or equal to" in spoken
    assert "less than" in spoken
    assert "zero" in spoken
    assert spoken.startswith("are ") or "are is" in spoken


def test_simple_inequalities():
    assert "less than" in speak_math_expr("r < b")
    assert "greater than" in speak_math_expr("r > b")
    assert "less than or equal to" in speak_math_expr(r"r \leq b")
    assert speak_math_expr("r < b").startswith("are is less than")


def test_fraction_three_fourths():
    assert speak_math_expr("3/4") == "three fourths"
    assert "one half" in speak_math_expr(r"\frac{1}{2}")
    assert "divided by" in speak_math_expr("a/b")


def test_powers_and_roots():
    assert "squared" in speak_math_expr("x^2")
    assert "squared" in speak_math_expr("x²")
    assert "cubed" in speak_math_expr("x^3")
    assert "square root of" in speak_math_expr(r"\sqrt{x}")
    assert "square root of" in speak_math_expr("√x")


def test_quadratic_formula():
    spoken = speak_math_expr(r"x = (-b \pm \sqrt{b^2-4ac}) / 2a")
    assert "equals" in spoken
    assert "plus or minus" in spoken
    assert "square root of" in spoken
    assert "squared" in spoken
    assert "divided by" in spoken
    assert "negative" in spoken
    assert "$" not in spoken
    assert "±" not in spoken
    assert "√" not in spoken


def test_pythagoras_and_circle():
    spoken = speak_math_expr("c² = a² + b²")
    assert "squared" in spoken
    assert "equals" in spoken
    assert "plus" in spoken
    circle = speak_math_expr("A = πr²")
    assert "pi" in circle
    assert "squared" in circle
    assert "equals" in circle


def test_euclidean_steps_keep_pauses():
    from processors.naturalizer import ResponseNaturalizerProcessor

    stepped = (
        "Let's try 84 and 30:\n"
        "84 = 30 × 2 + 24\n"
        "30 = 24 × 1 + 6\n"
        "24 = 6 × 4 + 0\n"
        "so the HCF is 6."
    )
    cleaned = ResponseNaturalizerProcessor._clean(
        ResponseNaturalizerProcessor(add_starters=False),
        stepped,
    )
    assert "\n" not in cleaned
    assert "equals" in cleaned
    assert "times" in cleaned
    assert "84" in cleaned or "eighty-four" in cleaned
    assert "new line" not in cleaned.lower()


def test_delimited_math_in_prose_does_not_leak_latex():
    spoken = speak_for_tts(
        r"we can write \[ a = bq + r \] where q is the quotient, "
        r"and $0 \leq r < b$."
    )
    assert r"\[" not in spoken
    assert r"\]" not in spoken
    assert "$" not in spoken
    assert "<" not in spoken
    assert "equals" in spoken
    assert "less than" in spoken
    assert "greater than or equal to" in spoken
    assert r"\leq" not in spoken
    assert "quotient" in spoken


def test_ordinary_english_is_unchanged():
    prose = "Let's solve this equation step by step."
    assert speak_for_tts(prose) == prose
    spoken = speak_for_tts("This condition makes the representation unique.")
    assert "ay" not in spoken
    assert "This condition makes the representation unique." in spoken


def test_ordinary_english_words_are_never_letter_products():
    for word in (
        "remainder",
        "divisor",
        "quotient",
        "coefficient",
        "polynomial",
        "equation",
        "expression",
        "variable",
        "constant",
        "factor",
        "solution",
        "example",
        "question",
        "answer",
        "relationship",
        "division",
        "quadratic",
    ):
        spoken = speak_for_tts(word)
        assert spoken == word
        assert "times" not in spoken
        spoken_expr = speak_math_expr(word)
        assert "times" not in spoken_expr
        assert spoken_expr == word


def test_required_english_sentences():
    assert speak_for_tts("The remainder is less than the divisor.") == (
        "The remainder is less than the divisor."
    )
    assert speak_for_tts("The quotient is 12.") == "The quotient is twelve."
    assert speak_for_tts("The coefficient of x is 5.") == (
        "The coefficient of ex is five."
    )
    assert speak_for_tts("The polynomial has two zeros.") == (
        "The polynomial has two zeros."
    )
    assert speak_for_tts("The solution is correct.") == "The solution is correct."
    assert speak_for_tts("Let's find the remainder.") == "Let's find the remainder."
    assert speak_for_tts("The divisor is b.") == "The divisor is b."
    assert speak_for_tts("The quotient is q.") == "The quotient is cue."


def test_delimited_english_is_not_parsed_as_math():
    spoken = speak_for_tts(r"\[ The remainder is less than the divisor. \]")
    assert "remainder" in spoken
    assert "times" not in spoken
    assert "divisor" in spoken
    wrapped = speak_for_tts(r"\[ a = bq + r, where r is the remainder \]")
    assert "remainder" in wrapped
    assert "r times e times m" not in wrapped
    assert "ay equals bee times cue plus are" in wrapped
    assert "remainder" in wrapped


def test_mixed_english_and_math():
    mixed = speak_for_tts("The remainder r satisfies 0 ≤ r < b.")
    assert "remainder" in mixed
    assert "times" not in mixed.split("remainder")[0]
    assert "are is greater than or equal to zero and less than bee" in mixed

    assert speak_for_tts("Here, a is the divisor and r is the remainder.") == (
        "Here, a is the divisor and r is the remainder."
    )

    lemma = speak_for_tts(
        "The quotient q and remainder r satisfy a = bq + r."
    )
    assert "quotient" in lemma
    assert "remainder" in lemma
    assert "ay equals bee times cue plus are" in lemma
    assert "r times e" not in lemma

    poly = speak_for_tts("The polynomial x² + bx + c has two zeros.")
    assert "polynomial" in poly
    assert "ex squared" in poly
    assert "bee ex" in poly
    assert "see" in poly
    assert "two zeros" in poly
    assert "p times o" not in poly


def test_relationship_and_lemma_titles_stay_english():
    title = "relationship between zeros and coefficients"
    assert speak_for_tts(title) == title
    lemma = "Euclid's division lemma"
    assert speak_for_tts(lemma).lower() == lemma.lower() or "division lemma" in speak_for_tts(lemma)


def test_three_ab_is_a_product_not_a_word():
    spoken_ab = speak_math_expr("3ab")
    assert "ay" in spoken_ab
    assert "bee" in spoken_ab
    spoken = speak_math_expr("3ab + c")
    assert "three" in spoken
    assert "see" in spoken
    assert "times" not in spoken.split("three")[0]


def _assert_not_digit_power(spoken: str) -> None:
    low = spoken.lower()
    assert "x two" not in low
    assert "x three" not in low
    assert "x four" not in low
    assert "b two" not in low
    assert re.search(r"\bx\s*2\b", low) is None
    assert re.search(r"\bx\s*3\b", low) is None


def test_required_powers_exact():

    assert speak_math_expr("x²") == "ex squared"
    assert speak_math_expr("x^2") == "ex squared"
    assert speak_math_expr("x³") == "ex cubed"
    assert speak_math_expr("x^3") == "ex cubed"
    assert speak_math_expr("x⁴") == "ex to the fourth power"
    assert speak_math_expr("x^4") == "ex to the fourth power"
    assert speak_math_expr("xⁿ") == "ex to the nth power"
    for src in ("x²", "x^2", "x³", "x^3", "x⁴", "x^4"):
        spoken = speak_for_tts(src)
        assert "squared" in spoken or "cubed" in spoken or "fourth" in spoken
        _assert_not_digit_power(spoken)
        assert "²" not in spoken
        assert "^" not in spoken


def test_required_polynomials_and_lemma():
    poly = speak_math_expr("2x² + 5x + 3 = 0")
    assert poly.lower() == "two ex squared plus five ex plus three equals zero"
    assert speak_math_expr("ax² + bx + c = 0").lower() == (
        "ay ex squared plus bee ex plus see equals zero"
    )
    cubic = speak_math_expr("x³ - 3x² + 2x - 8 = 0")
    assert "cubed" in cubic
    assert "squared" in cubic
    assert "minus" in cubic
    assert "equals zero" in cubic
    _assert_not_digit_power(cubic)

    lemma = speak_math_expr("a = bq + r")
    assert lemma == "ay equals bee times cue plus are"

    ineq = speak_math_expr("0 ≤ r < b")
    assert ineq == "are is greater than or equal to zero and less than bee"


def test_required_fractions_roots_formula():
    assert speak_math_expr("-b/a") == "negative bee divided by ay"
    assert speak_math_expr("3/4") == "three fourths"
    assert speak_math_expr("√x") == "the square root of ex"
    disc = speak_math_expr("√(b² - 4ac)")
    assert disc == "the square root of bee squared minus four ay see"

    qf = speak_math_expr("(-b ± √(b² - 4ac))/2a")
    assert "negative bee" in qf
    assert "plus or minus" in qf
    assert "square root of" in qf
    assert "squared" in qf
    assert "all divided by" in qf
    assert "bee" in qf
    _assert_not_digit_power(qf)


def test_required_zeros_coefficients_and_subscripts():
    assert speak_math_expr("α + β = -b/a") == (
        "The sum of alpha and beta is equal to negative bee divided by ay."
    )
    assert speak_math_expr("αβ = c/a") == (
        "The product of alpha and beta is equal to see divided by ay."
    )
    assert speak_math_expr("α + β + γ = -b/a") == (
        "The sum of alpha, beta, and gamma is equal to negative bee divided by ay."
    )
    assert speak_math_expr("αβ + βγ + γα = c/a") == (
        "The sum of the pairwise products is equal to see divided by ay."
    )
    assert speak_math_expr("αβγ = -d/a") == (
        "The product of alpha, beta, and gamma is equal to negative dee divided by ay."
    )
    assert speak_math_expr(r"\alpha + \beta = -\frac{b}{a}") == (
        "The sum of alpha and beta is equal to negative bee divided by ay."
    )
    assert speak_math_expr("x₁") == "ex one"
    assert speak_math_expr("x₂") == "ex two"
    assert speak_math_expr("x_1") == "ex one"
    assert speak_math_expr("x_2") == "ex two"


def test_required_products():
    pair = speak_math_expr("(a+b)(a-b)")
    assert "plus" in pair
    assert "minus" in pair
    assert "multiplied by" in pair or "times" in pair
    twice = speak_math_expr("2(x+3)")
    assert twice == "two times the quantity ex plus three"


def test_prose_x_squared_not_x_two():
    spoken = speak_for_tts("What does x² mean? x^2 is x multiplied by itself.")
    assert "squared" in spoken
    _assert_not_digit_power(spoken)
    assert "multiplied by itself" in spoken


def test_euclid_lemma_line_adds_where():
    spoken = speak_for_tts("a = bq + r, 0 ≤ r < b")
    assert spoken == (
        "ay equals bee times cue plus are, where "
        "are is greater than or equal to zero and less than bee"
    )
    assert speak_math_expr("a = bq + r, 0 ≤ r < b") == spoken


def test_tts_pipeline_does_not_send_digit_powers():
    from processors.naturalizer import ResponseNaturalizerProcessor

    cleaned = ResponseNaturalizerProcessor._clean(
        ResponseNaturalizerProcessor(add_starters=False),
        "Here, $x^2$ and x² both appear, and 2x² + 5x + 3 = 0.",
    )
    _assert_not_digit_power(cleaned)
    assert "squared" in cleaned
    assert "²" not in cleaned
    assert "^2" not in cleaned


def test_llm_prose_math_is_repaired_faithfully():
    spoken = speak_for_tts("Here x to the power of two grows fast, and b over a is the ratio.")
    assert "ex squared" in spoken
    assert "to the power of two" not in spoken
    assert "b divided by a" in spoken
    assert "b over a" not in spoken


def test_prose_repair_does_not_touch_normal_english():
    for prose in (
        "Let's go over this again.",
        "Think it over before answering.",
        "Moreover, the graph is symmetric.",
    ):
        assert speak_for_tts(prose) == prose


def test_board_formula_is_spoken_as_teacher():
    spoken = speak_for_tts(
        "If alpha and beta are the zeros, they satisfy:\n"
        "$α + β = -b/a$\n"
        "and their product is given by:\n"
        "$αβ = c/a$"
    )
    assert "The sum of alpha and beta is equal to negative bee divided by ay." in spoken
    assert "The product of alpha and beta is equal to see divided by ay." in spoken
    assert "over a" not in spoken.lower()


def test_latex_text_command_is_a_word_not_a_product():
    spoken = speak_for_tts(r"\( \text{sum} = -\frac{b}{a}\)")
    assert "sum equals negative bee divided by ay" in spoken
    assert "times u times" not in spoken


def test_unicode_fraction_slash_and_hyphen_are_real_maths():
    spoken = speak_for_tts("using \u2011b\u2044a for the sum")
    assert "negative bee divided by ay" in spoken
    assert "\u2044" not in spoken
    assert "\u2011" not in spoken


def test_comma_separated_formula_list_is_spoken_in_order():
    spoken = speak_for_tts(r"they relate to \(-\frac{b}{a},\;\frac{c}{a},\;-\frac{d}{a}\)")
    assert (
        "negative bee divided by ay, see divided by ay, and negative dee divided by ay"
        in spoken
    )
    assert "times a" not in spoken


def test_identity_inside_a_sentence_keeps_the_grammar():
    spoken = speak_for_tts("their product is αβ = c/a and that is the rule.")
    assert "their product is alpha beta equals see divided by ay" in spoken
    assert "is The product of" not in spoken


def test_factored_form_names_each_bracket():
    spoken = speak_for_tts("write it as a(x − α)(x − β) and compare")
    assert (
        "ay times the quantity ex minus alpha, times the quantity ex minus beta"
        in spoken
    )


def test_bare_operators_are_never_silent():
    spoken = speak_for_tts("the quadratic 3x² + 5x − 2")
    assert "plus" in spoken
    assert "minus" in spoken
    assert "+" not in spoken
    assert "squared" in spoken


def test_dashes_in_ordinary_sentences_are_not_minus():
    prose = "Let's look at an example - it will help. The cost was 40-50 rupees."
    assert speak_for_tts(prose) == prose


def test_subscripted_variables_multiply_audibly():
    spoken = speak_for_tts("$x_1 x_2 = 12$")
    assert "ex one times ex two equals twelve" in spoken


def test_teacher_equation_pacing_has_no_ssml():
    from processors.naturalizer import ResponseNaturalizerProcessor

    cleaned = ResponseNaturalizerProcessor._clean(
        ResponseNaturalizerProcessor(add_starters=False),
        "x = (-b ± √(b² - 4ac)) / 2a",
    )
    assert "<break" not in cleaned
    assert "plus or minus" in cleaned.lower()
    assert "bee" in cleaned
    assert "squared" in cleaned
    _assert_not_digit_power(cleaned)


def test_undelimited_latex_frac_is_spoken_not_read_literally():
    spoken = speak_for_tts(r"\frac{3929}{763}")
    assert spoken == (
        "three thousand nine hundred twenty-nine divided by "
        "seven hundred sixty-three"
    )
    assert r"\frac" not in spoken
    assert "{" not in spoken
    assert "}" not in spoken


def test_undelimited_negative_frac_uses_letter_names():
    spoken = speak_for_tts(r"\frac{-b}{a}")
    assert spoken == "negative bee divided by ay"
    assert r"\frac" not in spoken


def test_scaled_slash_fractions_are_implicit_products():
    spoken = speak_for_tts("12(3929/763) - 23(159/763)")
    assert spoken == (
        "twelve times three thousand nine hundred twenty-nine divided by "
        "seven hundred sixty-three minus twenty-three times one hundred "
        "fifty-nine divided by seven hundred sixty-three"
    )
    assert "(" not in spoken
    assert "/" not in spoken


def test_math_variables_x_and_y_are_letter_names():
    assert "why" in speak_for_tts("$y$")
    assert speak_for_tts("y").lower() == "why"
    assert "ex" in speak_for_tts("$x$")
    assert speak_for_tts("x").lower() == "ex"


def test_lemma_variables_are_letter_names():
    spoken = speak_for_tts("a = bq + r")
    assert spoken == "ay equals bee times cue plus are"
    assert "bq" not in spoken


def test_remainder_is_never_spelled_as_letters():
    spoken = speak_for_tts("The remainder is less than the divisor.")
    assert spoken == "The remainder is less than the divisor."
    assert "are ee em" not in spoken
    assert "times" not in spoken


def test_nested_latex_frac_is_spoken():
    spoken = speak_for_tts(r"\frac{\frac{1}{2}}{3}")
    assert "divided by" in spoken
    assert r"\frac" not in spoken
    assert "{" not in spoken


def test_quadratic_formula_bare_latex():
    """Visual LaTeX without $...$ must not reach TTS as \\frac, \\sqrt, or b^2."""
    visual = r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
    spoken = speak_for_tts(visual)
    assert spoken == (
        "ex equals negative bee, plus or minus the square root of "
        "bee squared minus four ay see, all divided by two ay"
    )
    assert r"\frac" not in spoken
    assert r"\sqrt" not in spoken
    assert "{" not in spoken
    assert "^" not in spoken
    assert "b two" not in spoken.lower()
    assert "times" not in spoken.split("four")[-1][:20]


def test_quadratic_formula_delimited():
    spoken = speak_for_tts(r"$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$")
    assert "plus or minus" in spoken
    assert "square root of" in spoken
    assert "squared" in spoken
    assert "all divided by" in spoken
    assert r"\frac" not in spoken


def test_frac_negative_b_over_two_a():
    spoken = speak_for_tts(r"\frac{-b}{2a}")
    assert "negative bee" in spoken
    assert "divided by" in spoken
    assert "two ay" in spoken
    assert r"\frac" not in spoken


def test_frac_b_squared_minus_four_ac_over_two_a():
    spoken = speak_for_tts(r"\frac{b^2-4ac}{2a}")
    assert "bee squared minus four ay see, all divided by two ay" == spoken


def test_single_variables_use_letter_names():
    assert speak_for_tts("$x$").startswith("ex")
    assert speak_for_tts("$y$") == "why."
    assert speak_for_tts("$a$") == "ay."
    assert speak_for_tts("$b$") == "bee."
    assert speak_for_tts("$c$") == "see."
    assert speak_for_tts("$d$") == "dee."
    assert speak_for_tts("$r$") == "are."
    assert speak_for_tts("$q$") == "cue."


def _bare_math_y(text: str) -> bool:
    import re

    return bool(re.search(r"(?<![A-Za-z])y(?![A-Za-z])", text, re.I))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("y = 2", "why equals two"),
        ("x + y = 5", "ex plus why equals five"),
        ("2y + 3 = 7", "two why plus three equals seven"),
        ("y²", "why squared"),
        ("The value of y is 5.", "The value of why is five."),
        (r"\frac{x+y}{2}", "ex plus why, all divided by two"),
        ("𝑦 = 2", "why equals two"),
        ("𝒚 = 2", "why equals two"),
        ("x + 𝑦 = 5", "ex plus why equals five"),
    ],
)
def test_mathematical_y_is_pronounced_why(source, expected):
    spoken = speak_for_tts(source)
    assert spoken == expected
    assert not _bare_math_y(spoken)


@pytest.mark.parametrize(
    "source",
    [
        "Why is this equation important?",
        "Yes, exactly.",
        "Really?",
    ],
)
def test_english_words_with_y_are_unchanged(source):
    assert speak_for_tts(source) == source


def test_naturalizer_final_tts_has_why_not_bare_y():
    from processors.naturalizer import ResponseNaturalizerProcessor

    processor = ResponseNaturalizerProcessor(add_starters=False)
    for source in ("y = 2", "The value of y is 5.", "𝑦 = 2"):
        cleaned = processor._clean(source)
        assert "why" in cleaned.lower()
        assert not _bare_math_y(cleaned)

