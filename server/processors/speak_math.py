"""
Deterministic math → spoken English for TTS.

The visual transcript keeps LaTeX / notation. Only the Cartesia path
uses this layer — no extra LLM call.
"""

from __future__ import annotations

import re
import unicodedata

_LETTER_NAMES = {
    "a": "ay",
    "b": "bee",
    "c": "see",
    "d": "dee",
    "e": "ee",
    "f": "eff",
    "g": "jee",
    "h": "h",
    "i": "eye",
    "j": "jay",
    "k": "kay",
    "l": "ell",
    "m": "em",
    "n": "en",
    "o": "oh",
    "p": "pee",
    "q": "cue",
    "r": "are",
    "s": "ess",
    "t": "tee",
    "u": "you",
    "v": "vee",
    "w": "double you",
    "x": "ex",
    "y": "why",
    "z": "zed",
}

_SMALL = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)
_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)
_ORDINAL_POWER = {
    0: "zeroth",
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
}
_SUPER_CHAR = {
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "ⁿ": "n",
}
_SUB_CHAR = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_GREEK_CHARS = set("αβγΔδπθ")
# Algebraic atoms for *region detection*. Latin runs longer than two letters
# are English words (remainder, coefficient), not implicit products.
_ALG_TERM = (
    r"(?:-?\d+[A-Za-zαβγπθΔδ]{1,4}[²³⁴⁵⁶⁷⁸⁹ⁿ₀-₉]*|"
    r"[A-Za-zαβγπθΔδ]{1,2}[²³⁴⁵⁶⁷⁸⁹ⁿ₀-₉]*|"
    r"-?\d+[²³⁴⁵⁶⁷⁸⁹ⁿ]?)"
)

_ORDINAL = {
    2: ("half", "halves"),
    3: ("third", "thirds"),
    4: ("fourth", "fourths"),
    5: ("fifth", "fifths"),
    6: ("sixth", "sixths"),
    7: ("seventh", "sevenths"),
    8: ("eighth", "eighths"),
    9: ("ninth", "ninths"),
    10: ("tenth", "tenths"),
}

_CONSTANTS = {
    "π": "pi",
    "pi": "pi",
    "θ": "theta",
    "theta": "theta",
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "Δ": "delta",
    "δ": "delta",
    "∞": "infinity",
    "sin": "sine",
    "cos": "cosine",
    "tan": "tan",
    "log": "log",
    "ln": "natural log",
    "hcf": "H C F",
    "lcm": "L C M",
    "gcd": "G C D",
}

_OP_FORWARD = {
    "<": "less than",
    ">": "greater than",
    "≤": "less than or equal to",
    "≥": "greater than or equal to",
    "≠": "not equal to",
}
_OP_INVERSE = {
    "<": "greater than",
    ">": "less than",
    "≤": "greater than or equal to",
    "≥": "less than or equal to",
    "≠": "not equal to",
}

_MATH_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.S)
_MATH_BRACKET = re.compile(r"\\\[(.+?)\\\]", re.S)
_MATH_PAREN = re.compile(r"\\\((.+?)\\\)", re.S)
_MATH_INLINE = re.compile(r"(?<!\$)\$(?!\$)(.+?)\$")

_CHAINED_INEQ = re.compile(
    r"^\s*(.+?)\s*(≤|≥|<|>|≠)\s*(.+?)\s*(≤|≥|<|>|≠)\s*(.+?)\s*$"
)
_SIMPLE_INEQ = re.compile(r"^\s*(.+?)\s*(≤|≥|<|>|≠)\s*(.+?)\s*$")

_BARE_CHAINED = re.compile(
    r"(?<![A-Za-z])((?:-?\d+|[A-Za-z])\s*(?:≤|≥|<|>|≠)\s*(?:-?\d+|[A-Za-z])"
    r"\s*(?:≤|≥|<|>|≠)\s*(?:-?\d+|[A-Za-z]))"
)
_BARE_SIMPLE_INEQ = re.compile(
    r"(?<![A-Za-z])((?:-?\d+|[A-Za-z])\s*(?:≤|≥|<|>|≠)\s*(?:-?\d+|[A-Za-z]))(?![A-Za-z])"
)
_BARE_EQUATION = re.compile(
    r"(?<![A-Za-z0-9])("
    rf"{_ALG_TERM}"
    rf"(?:\s*[+\-±]\s*{_ALG_TERM})*"
    r"\s*=\s*"
    r"[-+(A-Za-z0-9_²³⁴⁵⁶⁷⁸⁹ⁿ₀-₉αβγπθΔδ√±×·*/\\) \t^]+"
    r")"
)
_BARE_FACTORED = re.compile(
    r"(?<![A-Za-z0-9])(-?\d*\s*[A-Za-zαβγ]?\s*(?:\([^()]{1,40}\)\s*){2,})"
)
_BARE_FRACTION = re.compile(
    r"(?<![A-Za-z0-9/])(-?[A-Za-zαβγ]|-?\d+)/([A-Za-zαβγ]|\d+)(?![A-Za-z0-9/])"
)
# 12(3929/763) or 12(\frac{3929}{763}) - 23(...). Must run before leftover
# integer-speaking, or the braces around a LaTeX fraction survive as TTS junk.
_BARE_SCALED_GROUP = re.compile(
    r"(?<![A-Za-z0-9])("
    r"-?\d+\s*\([^()]{1,80}\)"
    r"(?:\s*[+\-±]\s*-?\d+\s*\([^()]{1,80}\))*"
    r")"
)
_BARE_LATEX_FRAC_CMD = re.compile(r"\\(?:d|t)?frac\s*\{")
# Isolated x/y/q/z in prose ("the value of y") — never articles like "a".
_ISOLATED_VAR = re.compile(r"(?<![A-Za-z])([xyqzXYQZ])(?![A-Za-z])")
# Polynomials without '=': x² + bx + c. Requires an operator so "remainder"
# never matches. Latin atoms are at most two letters (bx, ac), never words.
_BARE_POLYNOMIAL = re.compile(
    r"(?<![A-Za-z0-9])("
    rf"{_ALG_TERM}"
    rf"(?:\s*[+\-±]\s*{_ALG_TERM})+"
    r")(?!\s*=)"
)
_LEMMA_LINE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"[A-Za-z]\s*=\s*[A-Za-z]{2,}\s*\+\s*[A-Za-z]"
    r"\s*,\s*"
    r"0\s*≤\s*[A-Za-z]\s*<\s*[A-Za-z]"
    r")"
)
_POWER_CARET = re.compile(
    r"([A-Za-zαβγπθΔδ])\^\{?(2|3|4|5|n|[0-9]+)\}?(?![0-9A-Za-z])"
)
_POWER_SUPER = re.compile(r"([A-Za-zαβγπθΔδ])([²³⁴⁵⁶⁷⁸⁹ⁿ])")
_HTML_SUP = re.compile(r"<sup>(2|3|4|n|\d+)</sup>", re.I)
_HTML_SUB = re.compile(r"<sub>(\d+|[A-Za-z])</sub>", re.I)
_EQ_TRAILING_PROSE = re.compile(
    r"\s+\b(?:where|so|which|and|here|because|then|this|the|for|if|when|"
    r"with|that|while|after|before|using)\b.*$",
    re.I,
)

_LATEX_OPS = (
    (r"\leqslant", "≤"),
    (r"\geqslant", "≥"),
    (r"\leq", "≤"),
    (r"\geq", "≥"),
    (r"\neq", "≠"),
    (r"\ne", "≠"),
    (r"\le", "≤"),
    (r"\ge", "≥"),
    (r"\lt", "<"),
    (r"\gt", ">"),
    (r"\pm", "±"),
    (r"\times", "×"),
    (r"\cdot", "×"),
    (r"\div", "/"),
    (r"\infty", "∞"),
    (r"\pi", "π"),
    (r"\theta", "θ"),
    (r"\alpha", "α"),
    (r"\beta", "β"),
    (r"\gamma", "γ"),
    (r"\triangle", " triangle "),
    (r"\angle", " angle "),
    (r"\degree", " degrees "),
    (r"\circ", " degrees "),
    (r"\perp", " perpendicular to "),
    (r"\parallel", " parallel to "),
    (r"\left", ""),
    (r"\right", ""),
    (r"\displaystyle", ""),
    (r"\quad", " "),
    (r"\,", " "),
    (r"\;", " "),
    (r"\!", ""),
)


def _small_number(n: int) -> str:
    return _speak_integer(n)


def _speak_integer(n: int) -> str:
    if n < 0:
        return "negative " + _speak_integer(-n)
    if n <= 20:
        return _SMALL[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        if ones == 0:
            return _TENS[tens]
        return f"{_TENS[tens]}-{_SMALL[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = f"{_SMALL[hundreds]} hundred"
        if rest == 0:
            return head
        return f"{head} {_speak_integer(rest)}"
    if n < 10000:
        thousands, rest = divmod(n, 1000)
        head = f"{_speak_integer(thousands)} thousand"
        if rest == 0:
            return head
        return f"{head} {_speak_integer(rest)}"
    return str(n)


def _power_phrase(exp: str) -> str:
    exp = _SUPER_CHAR.get(exp, exp)
    if exp in {"2", 2}:
        return "squared"
    if exp in {"3", 3}:
        return "cubed"
    if exp in {"n", "N"}:
        return "to the nth power"
    if str(exp).isdigit():
        n = int(exp)
        ordinal = _ORDINAL_POWER.get(n, f"{n}th")
        return f"to the {ordinal} power"
    return f"to the {exp} power"


def _letter(ch: str) -> str:
    """Spell a mathematical variable as an English letter name.

    A bare Latin letter is pronounced by the TTS engine's current language, so
    an Indic voice reads "y" as "ee". Writing the English name ("why") makes
    the maths sound the same in every voice. Only reached from a detected math
    region or an isolated variable token, so ordinary prose ("remainder") is
    never spelled out. Greek uses _CONSTANTS.
    """
    if ch in _CONSTANTS:
        return _CONSTANTS[ch]
    return _LETTER_NAMES.get(ch.lower(), ch)


def _strip_outer_parens(expr: str) -> str:
    t = expr.strip()
    while t.startswith("(") and t.endswith(")"):
        depth = 0
        ok = True
        for i, c in enumerate(t):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0 and i != len(t) - 1:
                    ok = False
                    break
        if ok and depth == 0:
            t = t[1:-1].strip()
        else:
            break
    return t


def _split_top(expr: str, operators: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    ops = sorted(operators, key=len, reverse=True)
    while i < len(expr):
        c = expr[i]
        if c in "([{":
            depth += 1
            buf.append(c)
            i += 1
            continue
        if c in ")]}":
            depth -= 1
            buf.append(c)
            i += 1
            continue
        if depth == 0:
            matched = False
            for op in ops:
                if expr.startswith(op, i):
                    # unary minus / plus at start of a part is not a splitter
                    if op in "+-" and not "".join(buf).strip():
                        break
                    parts.append("".join(buf))
                    buf = []
                    i += len(op)
                    matched = True
                    break
            if matched:
                continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return parts


def _is_complex_expr(expr: str) -> bool:
    t = _strip_outer_parens(expr)
    if any(sym in t for sym in ("±", "√", "×")):
        return True
    if "+" in t:
        return True
    # Binary minus only — a leading sign like -b is a simple numerator.
    return bool(re.search(r"[A-Za-z0-9αβγπθΔδ²³⁴ⁿ)]\s*-", t))


def _speak_numeric_fraction(num: int, den: int) -> str:
    if den < 0:
        num, den = -num, -den
    sign = "negative " if num < 0 else ""
    num = abs(num)
    if den in _ORDINAL:
        spoken_num = _small_number(num)
        singular, plural = _ORDINAL[den]
        unit = singular if num == 1 else plural
        if den == 2 and num == 1:
            return f"{sign}one half".strip()
        return f"{sign}{spoken_num} {unit}".strip()
    return f"{sign}{_small_number(num)} divided by {_small_number(den)}".strip()


def _matching_brace(text: str, open_idx: int) -> int | None:
    """Index of the closing brace matching ``text[open_idx] == '{'``."""
    if open_idx >= len(text) or text[open_idx] != "{":
        return None
    depth = 0
    for k in range(open_idx, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return None


def _frac_span_at(text: str, cmd_start: int) -> tuple[int, int] | None:
    """Span of one ``\\frac{...}{...}`` command, including nested braces."""
    m = _BARE_LATEX_FRAC_CMD.match(text, cmd_start)
    if not m:
        return None
    brace = text.find("{", m.start())
    if brace < 0:
        return None
    num_end = _matching_brace(text, brace)
    if num_end is None:
        return None
    pos = num_end + 1
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        return None
    den_end = _matching_brace(text, pos)
    if den_end is None:
        return None
    return m.start(), den_end + 1


def _all_frac_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for m in _BARE_LATEX_FRAC_CMD.finditer(text):
        span = _frac_span_at(text, m.start())
        if span:
            spans.append(span)
    return spans


def _innermost_frac_span(spans: list[tuple[int, int]]) -> tuple[int, int]:
    """The span that does not strictly contain another ``\\frac`` span."""

    def contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
        return outer[0] <= inner[0] and inner[1] <= outer[1] and outer != inner

    for span in spans:
        if not any(contains(span, other) for other in spans if other != span):
            return span
    return spans[0]


def _assignment_lhs_start(text: str, frac_start: int) -> int:
    """Include ``x = `` immediately before a bare ``\\frac`` when present."""
    window = text[max(0, frac_start - 40):frac_start]
    match = re.search(
        r"(?<![A-Za-z0-9=])([A-Za-zαβγ][A-Za-z0-9αβγ]*)\s*=\s*$",
        window,
    )
    if not match:
        return frac_start
    return frac_start - len(window) + match.start()


def _replace_latex_fracs_flatten(text: str) -> str:
    """Turn ``\\frac{a}{b}`` into ``(a)/(b)``, including nested ``{...}``."""
    while True:
        spans = _all_frac_spans(text)
        if not spans:
            return text
        start, end = _innermost_frac_span(spans)
        brace = text.find("{", start)
        num_end = _matching_brace(text, brace)
        den_brace = num_end + 1
        while den_brace < len(text) and text[den_brace].isspace():
            den_brace += 1
        den_end = _matching_brace(text, den_brace)
        num = text[brace + 1 : num_end]
        den = text[den_brace + 1 : den_end]
        text = text[:start] + f"({num})/({den})" + text[end:]


def _replace_innermost(pattern: re.Pattern, text: str, replacer) -> str:
    while True:
        match = pattern.search(text)
        if not match:
            return text
        text = text[: match.start()] + replacer(match) + text[match.end() :]


_UNICODE_MATH_SIGNS = (
    ("\u2044", "/"),   # fraction slash ⁄
    ("\u2215", "/"),   # division slash ∕
    ("\u2011", "-"),   # non-breaking hyphen ‑
    ("\u2212", "-"),   # minus sign −
    ("\u2013", "-"),   # en dash –
    ("\u00a0", " "),   # non-breaking space
    ("\u2009", " "),   # thin space
    ("\u2007", " "),
)


def normalize_math_signs(text: str) -> str:
    """Map look-alike unicode signs to ASCII so maths is not read literally."""
    # LLMs often emit mathematical italic/bold letters (𝑦, 𝒙). Fold only those
    # codepoints — a blanket NFKC would turn ² into "2" and break y² → squared.
    folded: list[str] = []
    for ch in text:
        if unicodedata.name(ch, "").startswith("MATHEMATICAL"):
            folded.append(unicodedata.normalize("NFKC", ch))
        else:
            folded.append(ch)
    text = "".join(folded)
    for src, dst in _UNICODE_MATH_SIGNS:
        text = text.replace(src, dst)
    return text


_TEXT_WORD_OPEN = "\u27e6"
_TEXT_WORD_CLOSE = "\u27e7"


def flatten_latex(expr: str) -> str:
    """Turn LaTeX commands into unicode / plain infix. Does not speak yet."""
    t = normalize_math_signs(expr.strip())
    t = t.replace("\n", " ")

    # Environments (cases, aligned, matrix). The \begin command itself is
    # stripped later, but the environment name would survive as a bare word
    # inside the formula and be spelled out letter by letter ("c a s e s").
    # The row separator becomes a comma so stacked equations stay separate
    # instead of running into one another.
    t = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", " ", t)
    t = t.replace("\\\\", " , ")
    t = t.replace("&", " ")

    # \text{sum} is an English word, not a product of s, u and m.
    t = re.sub(
        r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}",
        lambda m: f"{_TEXT_WORD_OPEN}{m.group(1).strip()}{_TEXT_WORD_CLOSE}",
        t,
    )

    t = t.replace(r"\{", "(").replace(r"\}", ")")

    t = _replace_innermost(
        re.compile(r"\\sqrt\{([^{}]*)\}"),
        t,
        lambda m: f"√({m.group(1)})",
    )
    t = re.sub(r"\\sqrt\s*\(([^)]+)\)", r"√(\1)", t)
    t = _replace_latex_fracs_flatten(t)
    t = re.sub(r"\^\{2\}", "²", t)
    t = re.sub(r"\^\{3\}", "³", t)
    t = re.sub(r"\^\{4\}", "⁴", t)
    t = re.sub(r"\^\{n\}", "ⁿ", t)
    t = re.sub(r"\^2\b", "²", t)
    t = re.sub(r"\^3\b", "³", t)
    t = re.sub(r"\^4\b", "⁴", t)
    t = re.sub(r"\^n\b", "ⁿ", t)
    t = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", t)
    t = re.sub(r"_\{([^{}]+)\}", r"_\1", t)
    for src, dst in (
        ("₁", "_1"),
        ("₂", "_2"),
        ("₃", "_3"),
        ("₄", "_4"),
        ("₅", "_5"),
        ("₆", "_6"),
        ("₇", "_7"),
        ("₈", "_8"),
        ("₉", "_9"),
        ("₀", "_0"),
    ):
        t = t.replace(src, dst)

    for src, dst in _LATEX_OPS:
        t = t.replace(src, dst)

    t = t.replace("<=", "≤").replace(">=", "≥").replace("!=", "≠")
    t = t.replace("·", "×").replace("*", "×")
    t = normalize_math_signs(t)
    t = t.replace("{", " ").replace("}", " ")
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = re.sub(r" {2,}", " ", t)
    return t.strip()


def _speak_power_token(token: str) -> str:
    if not token:
        return ""
    last = token[-1]
    if last in _SUPER_CHAR:
        return f"{_speak_atom(token[:-1])} {_power_phrase(last)}"
    m = re.match(r"^(.+)\^\((.+)\)$", token)
    if m:
        return f"{_speak_atom(m.group(1))} to the power of {speak_math_expr(m.group(2))}"
    m = re.match(r"^(.+)\^(.+)$", token)
    if m:
        return f"{_speak_atom(m.group(1))} {_power_phrase(m.group(2))}"
    return ""


def _speak_atom(token: str) -> str:
    token = token.strip()
    if not token:
        return ""
    if token.startswith(_TEXT_WORD_OPEN) and token.endswith(_TEXT_WORD_CLOSE):
        return token[1:-1].strip()
    powered = _speak_power_token(token)
    if powered:
        return powered
    if token in _CONSTANTS:
        return _CONSTANTS[token]
    if re.fullmatch(r"-?\d+", token):
        n = int(token)
        return _speak_integer(n) if abs(n) <= 9999 else token.lstrip("+")
    if re.fullmatch(r"-?\d+\.\d+", token):
        return token
    m = re.fullmatch(r"([A-Za-zαβγπθΔδ])_([A-Za-z0-9]+)", token)
    if m:
        rest = m.group(2)
        if rest.isdigit():
            rest_s = _speak_integer(int(rest)) if int(rest) <= 20 else rest
            return f"{_letter(m.group(1))} {rest_s}"
        rest_s = _small_number(int(rest)) if rest.isdigit() and int(rest) <= 20 else rest
        return f"{_letter(m.group(1))} sub {rest_s}"
    if len(token) == 1 and token in _CONSTANTS:
        return _CONSTANTS[token]
    if len(token) == 1 and token.isalpha():
        return _letter(token)
    if token.lower() in _CONSTANTS:
        return _CONSTANTS[token.lower()]
    return token


_JUXTAPOSE_TOKEN = re.compile(
    r"\u27e6[^\u27e7]*\u27e7|"
    r"sin|cos|tan|log|ln|hcf|lcm|gcd|pi|theta|"
    r"π|θ|α|β|γ|Δ|δ|∞|"
    r"\d+(?:\.\d+)?|"
    r"[A-Za-z]+(?:_[A-Za-z0-9]+)?(?:[²³⁴⁵⁶⁷⁸⁹ⁿ]|\^[A-Za-z0-9]+)?|"
    r"[²³⁴⁵⁶⁷⁸⁹ⁿ]"
)
_LATIN_RUN = re.compile(
    r"^([A-Za-z]+)(_[A-Za-z0-9]+)?([²³⁴⁵⁶⁷⁸⁹ⁿ]|(\^[A-Za-z0-9]+))?$"
)
_SUBSCRIPT_ATOM = re.compile(r"[A-Za-zαβγ]_\d+")
_PROSE_WORDS = re.compile(
    r"\b("
    r"the|is|are|be|was|were|a|an|of|and|or|to|in|that|this|where|which|"
    r"because|then|when|for|with|from|less|than|must|can|we|let|write|"
    r"find|has|have|given|called|after|before|using|here|there"
    r")\b",
    re.I,
)


def _latin_base(token: str) -> str:
    match = _LATIN_RUN.match(token)
    return match.group(1) if match else ""


def _should_split_letter_run(base: str, *, after_number: bool, has_power: bool) -> bool:
    """Implicit products: 3ab, bq, ax². Never split remainder/coefficient."""
    if not base.isalpha() or base.lower() in _CONSTANTS or base in _CONSTANTS:
        return False
    if len(base) == 1:
        return False
    if after_number or has_power:
        return True
    return len(base) == 2


def _speak_split_letters(base: str, *, after_number: bool, power: str) -> str:
    pieces: list[str] = []
    for i, ch in enumerate(base):
        spoken = _letter(ch)
        if i == len(base) - 1 and power:
            spoken = f"{spoken} {power}"
        if i == 0:
            pieces.append(spoken)
            continue
        if after_number or ch.lower() in {"x", "y"} or power:
            pieces.append(spoken)
        else:
            pieces.append("times " + spoken)
    return " ".join(pieces)


def _speak_juxtapose_token(tok: str, *, after_number: bool) -> str:
    if tok.startswith(_TEXT_WORD_OPEN):
        return _speak_atom(tok)
    match = _LATIN_RUN.match(tok)
    if match and not match.group(2):
        base = match.group(1)
        super_ch = match.group(3) or ""
        power = ""
        if super_ch.startswith("^"):
            power = _power_phrase(super_ch[1:])
        elif super_ch:
            power = _power_phrase(super_ch)
        if _should_split_letter_run(base, after_number=after_number, has_power=bool(power)):
            return _speak_split_letters(base, after_number=after_number, power=power)
        if power:
            return f"{_speak_atom(base)} {power}"
    return _speak_atom(tok)


def _speak_juxtaposed(term: str) -> str:
    """Speak a product like 3ab or bq. Whole English words stay words."""
    term = term.strip()
    if not term:
        return ""
    tokens = _JUXTAPOSE_TOKEN.findall(term)
    if not tokens:
        return _speak_atom(term)
    joined: list[str] = []
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i else ""
        prev_is_num = bool(re.fullmatch(r"\d+(?:\.\d+)?", prev))
        seen_number = any(re.fullmatch(r"\d+(?:\.\d+)?", t) for t in tokens[:i])
        after_number = prev_is_num or seen_number
        spoken = _speak_juxtapose_token(tok, after_number=after_number)
        if i == 0:
            joined.append(spoken)
            continue
        prev_is_const = prev.lower() in _CONSTANTS or prev in _CONSTANTS
        tok_is_num = bool(re.fullmatch(r"\d+(?:\.\d+)?", tok))
        both_greek = prev in _GREEK_CHARS and tok in _GREEK_CHARS
        both_subscripted = bool(
            _SUBSCRIPT_ATOM.fullmatch(prev) and _SUBSCRIPT_ATOM.fullmatch(tok)
        )
        prev_base = _latin_base(prev)
        tok_base = _latin_base(tok)
        both_split_letters = (
            len(prev_base) == 1
            and len(tok_base) == 1
            and prev_base.isalpha()
            and tok_base.isalpha()
        )
        if both_subscripted:
            joined.append("times " + spoken)
        elif prev_is_num or tok_is_num or prev_is_const or seen_number:
            joined.append(spoken)
        elif both_greek:
            joined.append(spoken)
        elif both_split_letters:
            powered = bool(re.search(r"[²³⁴⁵⁶⁷⁸⁹ⁿ^]", prev + tok))
            poly_var = tok_base.lower() in {"x", "y"}
            if powered or poly_var:
                joined.append(spoken)
            else:
                joined.append("times " + spoken)
        else:
            joined.append(spoken)
    return " ".join(joined)


def _looks_like_prose(text: str) -> bool:
    """True when a string is an English clause, not a formula."""
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 2:
        return False
    if not _PROSE_WORDS.search(text):
        return False
    return any(len(w) >= 3 for w in words) or len(words) >= 3


def _has_formula_structure(text: str) -> bool:
    return bool(
        re.search(
            r"[=≠≤≥±√×·/]|[²³⁴⁵⁶⁷⁸⁹ⁿ^<>]|"
            r"\d[A-Za-z]|[A-Za-z]{1,2}\s*[+\-]\s*[A-Za-z0-9αβγ]|"
            r"[αβγπθΔδ]",
            text,
        )
    )


def _looks_like_math_expr(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    clause = re.match(r"(?i)(where|because|which|here|so|and then)\s+", t)
    if clause:
        rest = t[clause.end() :]
        return _has_formula_structure(rest) and not _looks_like_prose(rest)
    if _looks_like_prose(t) and not _has_formula_structure(t):
        return False
    return _has_formula_structure(t) or bool(
        re.fullmatch(r"-?\d+[A-Za-zαβγ].*", t)
    )


def _implicit_factors(term: str) -> list[str]:
    """Split 2(x+3) and (a+b)(a-b) into multiplied factors."""
    factors: list[str] = []
    buf: list[str] = []
    depth = 0
    for c in term:
        if c == "(":
            if depth == 0 and buf:
                factors.append("".join(buf))
                buf = []
            depth += 1
            buf.append(c)
            continue
        if c == ")":
            depth -= 1
            buf.append(c)
            if depth == 0:
                factors.append("".join(buf))
                buf = []
            continue
        buf.append(c)
    if buf:
        factors.append("".join(buf))
    return [f for f in factors if f]


def _speak_term(term: str) -> str:
    term = _strip_outer_parens(term.strip())
    if not term:
        return ""

    if term.startswith("√"):
        inner = term[1:].strip()
        inner = _strip_outer_parens(inner)
        return "the square root of " + speak_math_expr(inner)

    times_parts = [p for p in _split_top(term, ("×",)) if p.strip() != ""]
    if len(times_parts) > 1:
        return " times ".join(speak_math_expr(p) for p in times_parts)

    factors = (
        _implicit_factors(term)
        if re.search(r"[\dA-Za-zαβγπθΔδ)]\s*\(", term)
        else [term]
    )
    if len(factors) > 1:
        # A teacher names each bracket: "the quantity x minus alpha", and
        # pauses before the next one so the factors stay separate.
        pieces: list[str] = []
        _last_was_compound = False
        for index, factor in enumerate(factors):
            inner = _strip_outer_parens(factor.strip())
            spoken = speak_math_expr(inner)
            compound = len(_split_top(inner, ("+", "-"))) > 1
            if compound:
                spoken = "the quantity " + spoken
            if index:
                joiner = ", times " if _last_was_compound else " times "
                pieces.append(joiner + spoken)
            else:
                pieces.append(spoken)
            _last_was_compound = compound
        return "".join(pieces)

    powered = _speak_power_token(term)
    if powered and not re.search(r"[A-Za-z]{2,}", term.replace("pi", "").replace("theta", "")):
        # x², r² — not a whole juxtaposition string like πr²
        if _JUXTAPOSE_TOKEN.fullmatch(term) or len(term) <= 2:
            return powered

    return _speak_juxtaposed(term)


def _speak_sum(expr: str) -> str:
    expr = expr.strip()
    if not expr:
        return ""
    pieces: list[str] = []
    buf: list[str] = []
    depth = 0
    sign = ""
    i = 0
    while i < len(expr):
        c = expr[i]
        if c in "([{":
            depth += 1
            buf.append(c)
            i += 1
            continue
        if c in ")]}":
            depth -= 1
            buf.append(c)
            i += 1
            continue
        if depth == 0 and c in "+-" and "".join(buf).strip():
            term = "".join(buf).strip()
            spoken = _speak_term(term)
            if not pieces:
                pieces.append(("negative " + spoken) if sign == "-" else spoken)
            else:
                pieces.append(("minus " if sign == "-" else "plus ") + spoken)
            sign = c
            buf = []
            i += 1
            continue
        if depth == 0 and c in "+-" and not "".join(buf).strip() and not pieces:
            sign = "-" if c == "-" else ""
            i += 1
            continue
        buf.append(c)
        i += 1
    term = "".join(buf).strip()
    if term:
        spoken = _speak_term(term)
        if not pieces:
            pieces.append(("negative " + spoken) if sign == "-" else spoken)
        else:
            pieces.append(("minus " if sign == "-" else "plus ") + spoken)
    return " ".join(p for p in pieces if p)


def _try_inequality(expr: str) -> str | None:
    chained = _CHAINED_INEQ.match(expr)
    if chained:
        left, op1, mid, op2, right = chained.groups()
        if "=" in left or "=" in mid or "=" in right:
            return None
        return (
            f"{speak_math_expr(mid)} is {_OP_INVERSE[op1]} {speak_math_expr(left)}"
            f" and {_OP_FORWARD[op2]} {speak_math_expr(right)}"
        )
    simple = _SIMPLE_INEQ.match(expr)
    if simple:
        left, op, right = simple.groups()
        if "=" in left or "=" in right:
            return None
        if any(sym in left for sym in "+-×/") or any(sym in right for sym in "+-×/"):
            # still fine — "2x + 1 < 5"
            pass
        return (
            f"{speak_math_expr(left)} is {_OP_FORWARD[op]} {speak_math_expr(right)}"
        )
    return None


def _try_teacher_identity(raw: str) -> str | None:
    """Semantic teacher phrasing for Class 10 zeros/coefficients identities.

    Character-by-character 'alpha plus beta equals...' loses the relationship.
    """
    compact = re.sub(r"\s+", "", raw)

    def rhs(expr: str) -> str:
        return speak_math_expr(expr)

    m = re.fullmatch(r"αβ\+βγ\+γα=(.+)", compact)
    if m:
        return f"The sum of the pairwise products is equal to {rhs(m.group(1))}."

    m = re.fullmatch(r"αβγ=(.+)", compact)
    if m:
        return (
            "The product of alpha, beta, and gamma is equal to "
            f"{rhs(m.group(1))}."
        )

    m = re.fullmatch(r"αβ=(.+)", compact)
    if m:
        return f"The product of alpha and beta is equal to {rhs(m.group(1))}."

    m = re.fullmatch(r"α\+β\+γ=(.+)", compact)
    if m:
        return (
            "The sum of alpha, beta, and gamma is equal to "
            f"{rhs(m.group(1))}."
        )

    m = re.fullmatch(r"α\+β=(.+)", compact)
    if m:
        return f"The sum of alpha and beta is equal to {rhs(m.group(1))}."

    return None


def speak_math_expr(expr: str, *, inline: bool = False) -> str:
    """Speak a single mathematical expression in natural Class 10 English.

    ``inline`` means the formula sits inside a sentence, so the full teacher
    sentence ("The product of alpha and beta is equal to...") would break the
    grammar; the plain reading is used instead.
    """
    raw = _strip_outer_parens(flatten_latex(expr))
    if not raw:
        return ""

    # Delimiters sometimes wrap a whole English sentence. Do not parse it as
    # a product of letters. Real formulas still have structure (=, +, powers).
    if _looks_like_prose(raw) and not _has_formula_structure(raw):
        return _tidy(raw)

    if "," in raw:
        left, right = raw.split(",", 1)
        left, right = left.strip(), right.strip()
        if "=" in left and _try_inequality(right):
            return _tidy(
                speak_math_expr(left) + ", where " + speak_math_expr(right)
            )

    if not inline:
        identity = _try_teacher_identity(raw)
        if identity:
            return identity

    # A list of formulas: -b/a, c/a, -d/a — never English clauses.
    comma_parts = [p.strip() for p in _split_top(raw, (",",)) if p.strip()]
    if len(comma_parts) > 1 and all(
        not _try_inequality(p) for p in comma_parts
    ):
        if all(_looks_like_math_expr(p) for p in comma_parts):
            spoken_list = [speak_math_expr(p) for p in comma_parts]
            if len(spoken_list) > 2:
                return _tidy(
                    ", ".join(spoken_list[:-1]) + ", and " + spoken_list[-1]
                )
            return _tidy(", and ".join(spoken_list))
        if any(_looks_like_math_expr(p) for p in comma_parts):
            bits = [
                speak_math_expr(p) if _looks_like_math_expr(p) else p
                for p in comma_parts
            ]
            return _tidy(", ".join(bits))

    ineq = _try_inequality(raw)
    if ineq:
        return _tidy(ineq)

    eq_parts = _split_top(raw, ("=",))
    if len(eq_parts) >= 2:
        spoken_eq = " equals ".join(speak_math_expr(p) for p in eq_parts)
        return _tidy(spoken_eq)

    pm_parts = _split_top(raw, ("±",))
    if len(pm_parts) == 2:
        return _tidy(
            f"{speak_math_expr(pm_parts[0])}, plus or minus {speak_math_expr(pm_parts[1])}"
        )

    div_parts = _split_top(raw, ("/",))
    if len(div_parts) == 2:
        num, den = div_parts[0].strip(), div_parts[1].strip()
        num_u, den_u = _strip_outer_parens(num), _strip_outer_parens(den)
        if re.fullmatch(r"-?\d+", num_u) and re.fullmatch(r"-?\d+", den_u):
            return _tidy(_speak_numeric_fraction(int(num_u), int(den_u)))
        spoken_num = speak_math_expr(num_u)
        spoken_den = speak_math_expr(den_u)
        if _is_complex_expr(num):
            return _tidy(f"{spoken_num}, all divided by {spoken_den}")
        return _tidy(f"{spoken_num} divided by {spoken_den}")

    return _tidy(_speak_sum(raw))


def _tidy(text: str) -> str:
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" ,")


def _is_standalone(text: str, start: int, end: int) -> bool:
    """True when the formula owns its own line, as a board line does."""
    before = text[:start].rsplit("\n", 1)[-1].strip()
    after = text[end:].split("\n", 1)[0].strip(" .;")
    return not before and not after


def _replace_delimited(text: str) -> str:
    def _sub(match: re.Match) -> str:
        whole = match.string
        standalone = _is_standalone(whole, match.start(), match.end())
        spoken = speak_math_expr(match.group(1), inline=not standalone)
        if standalone and spoken and spoken[-1] not in ".,;:!?":
            rest = whole[match.end() :].split("\n", 1)[0].strip()
            # A board line needs a full stop, or TTS runs it into the next line.
            if not rest:
                spoken += "."
        return " " + spoken + " "

    text = _MATH_BLOCK.sub(_sub, text)
    text = _MATH_BRACKET.sub(_sub, text)
    text = _MATH_PAREN.sub(_sub, text)
    text = _MATH_INLINE.sub(_sub, text)
    return text


_MATH_WORD = r"(?:[a-z]|alpha|beta|gamma|delta|theta|\d+)"
_PROSE_OVER = re.compile(rf"\b({_MATH_WORD})\s+over\s+({_MATH_WORD})\b", re.I)
_PROSE_POWER = re.compile(
    r"\bto the power of\s+(two|three|four|five|n|2|3|4|5)\b", re.I
)
_PROSE_POWER_WORD = {
    "two": "squared",
    "2": "squared",
    "three": "cubed",
    "3": "cubed",
    "four": "to the fourth power",
    "4": "to the fourth power",
    "five": "to the fifth power",
    "5": "to the fifth power",
    "n": "to the nth power",
}


def _repair_spoken_math_prose(text: str) -> str:
    """Fix maths the model wrote as words, without inventing relationships.

    'x to the power of two' → 'x squared'; 'b over a' → 'b divided by a'.
    Purely a rendering fix: no mathematical meaning is added or changed.
    """
    text = _PROSE_POWER.sub(
        lambda m: _PROSE_POWER_WORD[m.group(1).lower()],
        text,
    )
    return _PROSE_OVER.sub(r"\1 divided by \2", text)


_LEFTOVER_PLUS = re.compile(r"(?<=\S)\s*\+\s*(?=\S)")
# Both sides must be short mathematical tokens, so dashes in ordinary
# sentences ("an example - it helps") are never read as "minus".
_LEFTOVER_MINUS = re.compile(
    r"(?<![A-Za-z0-9])"
    r"((?:\d+\s*)?[A-Za-zαβγπθ](?:\s+(?:squared|cubed))?|\d+|\))"
    r"\s+-\s+"
    r"(?=(?:\d+\s*)?[A-Za-zαβγπθ]\b|\d+\b|\()"
)


# Number + hyphen + English word: "20-minute", "5-year". Never a minus sign.
# Single-letter tails ("x-y", "a-b") stay algebraic and are spoken as minus.
_ENGLISH_COMPOUND_HYPHEN = re.compile(
    r"(?<![A-Za-z0-9.])(\d{1,4})-([A-Za-z]{3,})\b"
)


def _speak_english_compound_hyphens(text: str) -> str:
    """Say 20-minute as twenty-minute so TTS cannot read the hyphen as minus."""

    def _repl(match: re.Match) -> str:
        n = int(match.group(1))
        if abs(n) > 9999:
            return match.group(0)
        return f"{_speak_integer(n)}-{match.group(2)}"

    return _ENGLISH_COMPOUND_HYPHEN.sub(_repl, text)


def _speak_leftover_operators(text: str) -> str:
    """Say stray + and - signs that survived in prose.

    Cartesia either skips '+' or clicks through it, so 'a x squared + b x'
    loses the operator entirely. Minus is only spoken between mathematical
    tokens so ordinary dashes in English are left alone.
    """
    text = _LEFTOVER_PLUS.sub(" plus ", text)
    text = _LEFTOVER_MINUS.sub(r"\1 minus ", text)
    return text


def _speak_remaining_powers(text: str) -> str:
    """Convert leftover x^2 / x² in prose. Does not rewrite ordinary English."""

    def html_sup(match: re.Match) -> str:
        return " " + _power_phrase(match.group(1))

    text = _HTML_SUP.sub(html_sup, text)
    text = _HTML_SUB.sub(lambda m: " " + m.group(1), text)
    text = _POWER_CARET.sub(
        lambda m: f"{m.group(1)} {_power_phrase(m.group(2))}",
        text,
    )
    text = _POWER_SUPER.sub(
        lambda m: f"{m.group(1)} {_power_phrase(m.group(2))}",
        text,
    )
    return text


def _speak_bare_integers(text: str) -> str:
    """Say standalone 12 as twelve. Leave 3x / 2a glued to letters."""

    def _unary(match: re.Match) -> str:
        n = int(match.group(1))
        if n > 9999:
            return match.group(0)
        return "negative " + _speak_integer(n)

    # "-5" is a signed number. "40-50" and "twenty-minute" keep their hyphen:
    # the minus here must not be preceded by a letter or digit.
    text = re.sub(
        r"(?<![A-Za-z0-9])-(\d{1,4})(?!\.\d)(?![A-Za-z0-9])",
        _unary,
        text,
    )

    def _repl(match: re.Match) -> str:
        n = int(match.group(0))
        if abs(n) > 9999:
            return match.group(0)
        return _speak_integer(n)

    return re.sub(
        r"(?<![A-Za-z0-9.])(?<!\d-)(\d{1,4})(?!\.\d)(?!-\d)(?![A-Za-z0-9])",
        _repl,
        text,
    )


def speak_for_tts(text: str, *, speech_language: str | None = None) -> str:
    """Convert a tutor reply to speech. Leaves non-math prose intact.

    ``speech_language`` is accepted for callers that already pass the active
    TTS language; letter names are used in every language so "y" never becomes
    "ee" on an Indic voice.
    """
    if not text:
        return text
    return _speak_for_tts(text)


def _speak_undelimited_latex_fracs(text: str) -> str:
    """Speak ``\\frac{a}{b}`` (and ``x = \\frac{...}{...}``) without ``$...$``."""

    while True:
        spans = _all_frac_spans(text)
        if not spans:
            return text
        frac_start, frac_end = _innermost_frac_span(spans)
        start = _assignment_lhs_start(text, frac_start)
        raw = text[start:frac_end]
        spoken = speak_math_expr(raw)
        text = text[:start] + spoken + text[frac_end:]


def _speak_scaled_groups(text: str) -> str:
    """Speak 12(3929/763) - 23(159/763) as implicit products of fractions."""

    def replacer(match: re.Match) -> str:
        raw = match.group(1)
        inners = re.findall(r"\(([^()]*)\)", raw)
        if not inners:
            return match.group(0)
        if not any(re.search(r"[/+\-×=]|\\frac", inner) for inner in inners):
            return match.group(0)
        if any(_looks_like_prose(inner) for inner in inners):
            return match.group(0)
        return speak_math_expr(raw, inline=True)

    return _BARE_SCALED_GROUP.sub(replacer, text)


def _strip_leftover_latex(text: str) -> str:
    """Last-resort: backslashes and braces must never reach the voice."""
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    return text


def _speak_isolated_variables(text: str) -> str:
    return _ISOLATED_VAR.sub(lambda m: _letter(m.group(1)), text)


# Standalone mathematical y must never reach Cartesia as the bare letter "y"
# (Indic voices read it as "yee"). Word-boundary match skips English words.
_MATH_VARIABLE_Y = re.compile(r"(?<![A-Za-z])y(?![A-Za-z])", re.I)


def ensure_math_y_speech(text: str) -> str:
    """Final pass: spell mathematical variable y as the word 'why' for TTS."""
    if not text:
        return text
    return _MATH_VARIABLE_Y.sub("why", text)


def _speak_for_tts(text: str) -> str:
    text = normalize_math_signs(text)
    # Before polynomial detection: "20-minute" is English, not 20 minus mi.
    text = _speak_english_compound_hyphens(text)
    text = _replace_delimited(text)
    # Bare \\frac{...}{...} (often with nested \\sqrt) must be spoken before
    # _BARE_EQUATION, which stops at '{' and leaves "\frac" for TTS.
    text = _speak_undelimited_latex_fracs(text)

    def lemma_sub(match: re.Match) -> str:
        raw = match.group(1)
        parts = re.split(r"\s*,\s*", raw, maxsplit=1)
        if len(parts) != 2:
            return speak_math_expr(raw)
        return speak_math_expr(parts[0]) + ", where " + speak_math_expr(parts[1])

    text = _LEMMA_LINE.sub(lemma_sub, text)

    def chained_sub(match: re.Match) -> str:
        return speak_math_expr(match.group(1))

    text = _BARE_CHAINED.sub(chained_sub, text)
    text = _BARE_SIMPLE_INEQ.sub(chained_sub, text)

    def eq_sub(match: re.Match) -> str:
        expr = match.group(1)
        prose = _EQ_TRAILING_PROSE.search(expr)
        if prose:
            trimmed = expr[: prose.start()].strip()
            trailing = expr[prose.start() :]
        else:
            trimmed = expr.strip()
            trailing = ""
        inline = not _is_standalone(match.string, match.start(), match.end())
        return speak_math_expr(trimmed, inline=inline) + trailing

    # One pass only consumes the first equation on a line; the rest is returned
    # as prose, so repeat until every equation on the line has been spoken.
    for _ in range(3):
        spoken = _BARE_EQUATION.sub(eq_sub, text)
        if spoken == text:
            break
        text = spoken

    def factored_sub(match: re.Match) -> str:
        return " " + speak_math_expr(match.group(1), inline=True) + " "

    text = _BARE_FACTORED.sub(factored_sub, text)

    def poly_sub(match: re.Match) -> str:
        raw = match.group(1)
        # "40-50 rupees" is a range, not a polynomial.
        if not re.search(r"[A-Za-zαβγπθΔδ²³⁴⁵⁶⁷⁸⁹ⁿ]", raw):
            return match.group(0)
        # "20-minute": _ALG_TERM only eats "mi", leaving "nute". Do not
        # speak that fragment as 20 minus m i.
        rest = match.string[match.end() : match.end() + 1]
        if rest.isalpha() and re.search(r"\d-[A-Za-z]{1,2}$", raw):
            return match.group(0)
        return speak_math_expr(raw, inline=True)

    text = _BARE_POLYNOMIAL.sub(poly_sub, text)
    # Scaled groups like 12(3929/763) - 23(159/763).
    text = _speak_scaled_groups(text)

    def frac_sub(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        if left.lower() in {"and", "or", "w", "n"}:
            return match.group(0)
        return speak_math_expr(f"{left}/{right}")

    text = _BARE_FRACTION.sub(frac_sub, text)
    text = _speak_remaining_powers(text)
    text = _repair_spoken_math_prose(text)
    text = _speak_leftover_operators(text)

    # Leftover symbols TTS would swallow or read literally.
    # Never turn ²/³ into digits — that yields "x two" from Cartesia.
    text = text.replace("=", " equals ")
    text = text.replace("≤", " less than or equal to ")
    text = text.replace("≥", " greater than or equal to ")
    text = text.replace("≠", " not equal to ")
    text = text.replace("×", " times ")
    text = text.replace("·", " times ")
    text = text.replace("±", " plus or minus ")
    text = text.replace("√", " the square root of ")
    text = text.replace("²", " squared")
    text = text.replace("³", " cubed")
    text = text.replace("⁴", " to the fourth power")
    text = text.replace("⁵", " to the fifth power")
    text = text.replace("ⁿ", " to the nth power")
    text = text.replace("α", " alpha ")
    text = text.replace("β", " beta ")
    text = text.replace("γ", " gamma ")
    text = text.replace("π", " pi ")
    text = text.replace("θ", " theta ")
    text = text.replace("°", " degrees ")
    text = text.replace("<", " less than ")
    text = text.replace(">", " greater than ")
    text = text.replace(r"\[", " ")
    text = text.replace(r"\]", " ")
    text = text.replace(r"\(", " ")
    text = text.replace(r"\)", " ")
    text = text.replace("$", " ")
    text = _speak_isolated_variables(text)
    text = _speak_bare_integers(text)
    text = _strip_leftover_latex(text)
    text = ensure_math_y_speech(text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.strip()


def math_delimiters_unclosed(text: str) -> bool:
    """True when a streaming buffer is still inside $...$ / \\[...\\]."""
    t = _MATH_BLOCK.sub("", text)
    t = _MATH_BRACKET.sub("", t)
    t = _MATH_PAREN.sub("", t)
    t = _MATH_INLINE.sub("", t)
    if "$$" in t or r"\[" in t or r"\(" in t:
        return True
    return t.count("$") % 2 == 1
