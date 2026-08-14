"""Tutor / product FAQ knowledge — isolated from lesson content.

Deterministic retrieval only (regex). No extra LLM call. The existing tutor
LLM still speaks the reply in the student's active language, constrained to
the matched answer so it cannot invent capabilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

FAQCategory = Literal[
    "tutor_capability",
    "curriculum",
    "interaction",
    "language",
]

FAQ_KNOWLEDGE_MARKER = "[FAQ_KNOWLEDGE]"

_WS = re.compile(r"\s+", re.UNICODE)
_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'"})


def normalize_faq_text(text: str) -> str:
    value = (text or "").translate(_APOSTROPHES).lower().replace("\u200b", "")
    return _WS.sub(" ", value).strip()


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile(r"(?:" + "|".join(parts) + r")", re.I | re.UNICODE)


@dataclass(frozen=True)
class FAQEntry:
    id: str
    question: str
    answer: str
    category: FAQCategory
    patterns: tuple[re.Pattern[str], ...]
    #: True when the question is *about* the slide/lesson as a product feature.
    allow_lesson_reference: bool = False


# Grounded in the live product: Class 10 Mathematics, four algebra chapters,
# practice + hints, barge-in, typed chat, 1–5 min study breaks, en/hi/ta/te.
# English is catalogued but not available. Do not list other subjects/grades.

FAQS: tuple[FAQEntry, ...] = (
    FAQEntry(
        id="languages",
        question="Can I talk to you in Hindi/Tamil/Telugu?",
        answer=(
            "Yes. You can speak naturally in Hindi, English, Tamil, Telugu, "
            "or mix them the way you normally would."
        ),
        category="language",
        patterns=(
            _rx(
                r"\bcan i .{0,48}(?:hindi|tamil|telugu|english)\b",
                r"\bcan you (?:speak|talk|teach|reply).{0,24}"
                r"(?:hindi|tamil|telugu|english)\b",
                r"\bdo you (?:speak|understand|know|talk)\s+"
                r"(?:hindi|tamil|telugu|english)\b",
                r"\btalk to you in\s+(?:hindi|tamil|telugu|english)\b",
                r"\b(?:hindi|tamil|telugu)\s+(?:mein|me|la|lo|il)\b",
                r"हिंदी में|तमिल में|तेलुगु में|தமிழில்|తెలుగులో",
                r"\b(?:hinglish|tanglish|tenglish)\b",
            ),
        ),
    ),
    FAQEntry(
        id="interrupt",
        question="Can I interrupt you while you're speaking?",
        answer="Of course. Just start speaking and I'll stop and listen.",
        category="interaction",
        patterns=(
            _rx(
                r"\binterrupt\b",
                r"\bcut (?:you )?off\b",
                r"\bstop you\b",
                r"\bbarge in\b",
                r"\bwhile you(?:'re| are) speaking\b",
                r"\btalk over you\b",
            ),
        ),
    ),
    FAQEntry(
        id="type_instead",
        question="Can I type instead of speaking?",
        answer=(
            "Yes. You can type in the chat or talk out loud — both reach me "
            "the same way."
        ),
        category="interaction",
        patterns=(
            _rx(
                r"\btype\s+instead\b",
                r"\bcan i type\b",
                r"\btype (?:my|the) (?:question|answer|chat)\b",
                r"\binstead of speaking\b",
                r"\bwithout (?:talking|speaking|the mic)\b",
                r"\btyped? chat\b",
                r"टाइप",
            ),
        ),
    ),
    FAQEntry(
        id="study_break",
        question="Can I take a break while studying?",
        answer=(
            "Yes. Ask for a short study break — I can pause for one to five "
            "minutes, then we pick up the same lesson."
        ),
        category="interaction",
        patterns=(
            _rx(
                r"\bstudy breaks?\b",
                r"\bbreak while (?:studying|learning)\b",
                r"\bpause while (?:studying|learning)\b",
                r"\bdo you (?:have|support|allow) (?:a )?(?:study )?breaks?\b",
                r"\bcan i (?:pause|rest) (?:the lesson|while studying)\b",
                r"\bis there (?:a )?(?:study )?break\b",
            ),
        ),
    ),
    FAQEntry(
        id="current_slide",
        question="Can I ask questions about the current slide/content?",
        answer=(
            "Yes. 'This', 'that', or 'the slide' means what's on your screen "
            "right now — ask about it anytime."
        ),
        category="tutor_capability",
        allow_lesson_reference=True,
        patterns=(
            _rx(
                r"\bask (?:questions? )?about (?:the )?(?:current )?(?:slide|content|screen|lesson)\b",
                r"\bquestions? about (?:the )?(?:current )?(?:slide|content|screen)\b",
                r"\bcurrent slide\b",
                r"\bwhat's on (?:my|the) screen\b",
                r"\bon[- ]screen (?:content|lesson)\b",
            ),
        ),
    ),
    FAQEntry(
        id="hints_not_answers",
        question="Can you give me hints instead of the answer?",
        answer=(
            "Yes. Say you want a hint and I'll nudge you without giving the "
            "full answer. Ask for the answer only if you really want it."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bhints? instead\b",
                r"\binstead of (?:the |an )?answer\b",
                r"\bwithout (?:giving |telling )?(?:me )?(?:the )?answer\b",
                r"\bdo you (?:give|offer) hints?\b",
                r"\bcan you (?:just )?hint\b",
                r"\bhint not (?:the )?answer\b",
            ),
        ),
    ),
    FAQEntry(
        id="practice",
        question="Can I practice questions with you?",
        answer=(
            "Yes. After the lesson, use practice on the screen and we can work "
            "the questions together."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bpractice (?:questions? )?with you\b",
                r"\bcan i practice\b",
                r"\bcan we practice\b",
                r"\bdo you (?:have|offer) practice\b",
                r"\bpractice (?:mode|questions?)\b",
            ),
        ),
    ),
    FAQEntry(
        id="step_by_step",
        question="Can you solve a problem step by step?",
        answer=(
            "Yes. I can walk you through a problem one step at a time. If you'd "
            "rather try it yourself, ask for a hint instead."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bstep by step\b",
                r"\bstep-by-step\b",
                r"\bone step at a time\b",
                r"\bworked (?:solution|example)\b",
                r"\bsolve (?:a |problems? )?(?:problem )?step",
            ),
        ),
    ),
    FAQEntry(
        id="explain_concept",
        question="Can you explain a concept?",
        answer=(
            "Yes. I can explain the Class 10 maths concepts in this lesson — "
            "the idea on your screen, or one you name from these chapters."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bexplain a concept\b",
                r"\bexplain concepts?\b",
                r"\bdo you explain\b",
                r"\bcan you explain(?: a concept)?\s*[.?]?\s*$",
            ),
        ),
    ),
    FAQEntry(
        id="explain_again",
        question="Can you explain something again?",
        answer=(
            "Yes. Just say 'explain that again' or 'say it differently' and "
            "I'll rephrase — I won't restart a long lecture."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bexplain something again\b",
                r"\bask you to (?:explain|repeat) again\b",
                r"\bif i (?:want|ask) you to (?:explain|repeat)\b",
                r"\bcan you (?:repeat|rephrase) (?:things|something)\b",
            ),
        ),
    ),
    FAQEntry(
        id="dont_understand_question",
        question="What should I do if I don't understand a question?",
        answer=(
            "Say so. I can simplify it, give a hint, or explain it another way. "
            "Don't stay stuck — tell me which part is confusing."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bif i (?:don'?t|do not) understand\b",
                r"\bwhat (?:should|do) i do if\b",
                r"\bwhen i (?:don'?t|do not) understand\b",
                r"\bif a question (?:is hard|confus)",
            ),
        ),
    ),
    FAQEntry(
        id="class_grade",
        question="Which class/grade are you designed for?",
        answer="I'm designed for Class 10. That's the grade this lesson is built for.",
        category="curriculum",
        patterns=(
            _rx(
                r"\bwhich (?:class|grade)\b",
                r"\bwhat (?:class|grade)\b",
                r"\bclass(?:/|\s+or\s+)grade\b",
                r"\bdesigned for\b",
                r"\bfor (?:which |what )?class\b",
                r"\b(?:which|what) (?:standard|tenth)\b",
                r"कक्षा\s*(?:कौन|किस)",
            ),
        ),
    ),
    FAQEntry(
        id="subjects",
        question="Which subjects do you support?",
        answer=(
            "Right now I teach Class 10 Mathematics. English is listed but not "
            "available yet — I can't help with other subjects."
        ),
        category="curriculum",
        patterns=(
            _rx(
                r"\bwhich subjects?\b",
                r"\bwhat subjects?\b",
                r"\bsubjects? do you (?:support|teach|cover)\b",
                r"\bdo you (?:teach|support) (?:english|science|physics|chemistry|other)\b",
                r"\bonly maths?\b|\bonly math\b",
            ),
        ),
    ),
    FAQEntry(
        id="chapters_topics",
        question="What chapters/topics can I learn?",
        answer=(
            "In maths we can work through Real Numbers, Polynomials, Pair of "
            "Linear Equations in Two Variables, and Quadratic Equations — "
            "whichever chapter you've opened."
        ),
        category="curriculum",
        patterns=(
            _rx(
                r"\bwhich (?:chapters?|topics?)\b",
                r"\bwhat (?:chapters?|topics?)\b",
                r"\bchapters? (?:can i|do you)\b",
                r"\btopics? (?:can i|do you)\b",
                r"\bwhat can i learn\b",
                r"\bsyllabus\b",
            ),
        ),
    ),
    FAQEntry(
        id="what_can_you_help",
        question="What can you help me with?",
        answer=(
            "I can explain the concepts you're learning, work through problems "
            "step by step, give you hints when you're stuck, and help you "
            "practice. You can also interrupt me anytime if something isn't clear."
        ),
        category="tutor_capability",
        patterns=(
            _rx(
                r"\bwhat can you (?:help|do)\b",
                r"\bhow can you help\b",
                r"\bwhat do you do\b",
                r"\bhow do you help\b",
                r"\bwhat are you (?:for|here for)\b",
                r"\bhelp me with homework\b",
                r"\bcan you help with homework\b",
            ),
        ),
    ),
)

FAQ_BY_ID: dict[str, FAQEntry] = {entry.id: entry for entry in FAQS}

# Fast reject: ordinary tutoring has none of these product/meta cues.
_FAQ_HINT = _rx(
    r"\bwhat can you\b",
    r"\bhow can you help\b",
    r"\bwhat do you do\b",
    r"\bhow do you help\b",
    r"\bwhat are you (?:for|here for)\b",
    r"\bwhich (?:subject|class|grade|chapter|topic)",
    r"\bwhat (?:subject|class|grade|chapter|topic|chapters|topics)",
    r"\bcan (?:you|i)\b",
    r"\bdo you (?:support|teach|speak|give|have|explain|offer|allow)\b",
    r"\btype instead\b",
    r"\binterrupt\b",
    r"\bhindi\b|\btamil\b|\btelugu\b|\bhinglish\b",
    r"\bstudy breaks?\b",
    r"\bbreak while\b",
    r"\bcan we practice\b",
    r"\bif i (?:don'?t|do not) understand\b",
    r"\bwhat (?:should|do) i do if\b",
    r"\bstep by step\b",
    r"\bstep-by-step\b",
    r"\bhints? instead\b",
    r"\binstead of (?:the |an )?answer\b",
    r"\bpractice (?:questions? )?with you\b",
    r"\bcan i practice\b",
    r"\bcurrent slide\b",
    r"\bsyllabus\b",
    r"\bdesigned for\b",
    r"\bhelp me with homework\b",
    r"हिंदी|तमिल|तेलुगु|தமிழ்|తెలుగు|कक्षा|टाइप",
)

# Current-lesson asks must stay tutoring — not product FAQ.
_LESSON_OVERRIDE = _rx(
    r"\bthis (?:equation|problem|question|example|step|one|topic|formula|lemma|concept)\b",
    r"\bthat (?:equation|problem|question|example|step|concept|one|again)\b",
    r"\bthe (?:second|first|next|previous) step\b",
    r"\bhelp me with this\b",
    r"\bsolve this\b",
    r"\bexplain this\b",
    r"\bexplain that\b",
    r"\bwalk me through (?:this|the|it)\b",
    r"\bwhat (?:is|does) (?:this|that|b|a|c)\b",
    r"\bwhy (?:is|does|did|do) (?:this|that)\b",
)


def match_faq(utterance: str) -> FAQEntry | None:
    """Return the matching product FAQ, or None for ordinary tutoring.

    Lesson questions ('this equation', 'explain that again') are not FAQs.
    A miss is one hint-scan and a no-op — no added LLM.
    """
    text = normalize_faq_text(utterance)
    if not text or not _FAQ_HINT.search(text):
        return None
    override = bool(_LESSON_OVERRIDE.search(text))
    for entry in FAQS:
        if override and not entry.allow_lesson_reference:
            continue
        if any(pattern.search(text) for pattern in entry.patterns):
            return entry
    return None
