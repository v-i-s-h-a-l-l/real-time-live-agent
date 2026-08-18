"""Conversation policy — what a good human tutor would do next (no extra LLM)."""

from __future__ import annotations

from typing import Any, Callable

from tutor.faq import FAQEntry
from tutor.intent import is_interrupt_style, is_move_on_request, is_simple_factual
from tutor.practice import MAX_HINT_LEVEL, AnswerEvaluation, PracticeSnapshot
from tutor.scope import (
    APPLICATION_DOMAIN,
    APPLICATION_SUBJECT,
    is_short_refusal,
)
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
    TutorState,
)

_Handler = Callable[
    [StudentIntent, str, TutorState, str, dict[str, Any] | None],
    TutorDecision,
]

_PracticeBuilder = Callable[[StudentIntent, PracticeSnapshot], TutorDecision]

#: What each rung of the hint ladder is allowed to give away.
_HINT_LADDER: dict[int, str] = {
    1: "Give one small conceptual nudge — the idea to look at, not the numbers.",
    2: "Give a more specific hint that narrows the search, still not the answer.",
    3: "Walk them through the next single step, then hand it back to them.",
    MAX_HINT_LEVEL: (
        "They have struggled enough. Say you'll work it through together, show the "
        "reasoning in a couple of spoken steps, and end with the answer."
    ),
}


def _ladder_rung(level: int) -> str:
    return _HINT_LADDER.get(max(1, min(MAX_HINT_LEVEL, level)), _HINT_LADDER[1])


def _correct(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    harder = practice.recommended_difficulty > practice.difficulty
    follow_up = (
        " Then offer one that is a little harder — one short sentence, not a speech."
        if harder
        else " Then move them on without ceremony."
    )
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.EVALUATE,
        move=ConversationMove.CELEBRATE,
        response_length=ResponseLength.SHORT,
        strategy=(
            "They got it right. Confirm it warmly and briefly the way a person would "
            "('Exactly.', 'That's it.') and restate the answer once."
            + follow_up
            + " Do not re-teach the method and do not list the steps."
        ),
        allow_reveal_answer=False,
        check_understanding=False,
        evaluation=AnswerEvaluation.CORRECT.value,
    )


def _partially_correct(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.EVALUATE,
        move=ConversationMove.GUIDE,
        response_length=ResponseLength.GUIDED,
        strategy=(
            "Their reasoning is on the right track but the answer is incomplete. "
            "Say what they got right first, then point at the exact piece that is missing "
            "and ask one short question that gets them there. "
            "Do not say 'incorrect' and do not finish it for them."
        ),
        allow_reveal_answer=False,
        use_next_hint=practice.hint_level >= 1,
        check_understanding=False,
        evaluation=AnswerEvaluation.PARTIALLY_CORRECT.value,
        hint_level=practice.hint_level,
    )


def _incorrect(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.CORRECT if final else TeachingMode.SOCRATIC,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.MEDIUM if final else ResponseLength.GUIDED,
        strategy=(
            "That attempt is not right, but never say 'incorrect' or 'wrong'. "
            "Name the likely slip in their thinking in a few words. "
            + _ladder_rung(level)
            + (" Then wait for them." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.INCORRECT.value,
        hint_level=level,
    )


def _needs_hint(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.CORRECT if final else TeachingMode.HINT,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.MEDIUM if final else ResponseLength.GUIDED,
        strategy=(
            "They said they don't know. Take the pressure off in a few words "
            "('No worries — let's work through it together.'). "
            + _ladder_rung(level)
            + (" Then wait for them." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.NEEDS_HINT.value,
        hint_level=level,
    )


def _hint_request(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=StudentIntent.HINT,
        mode=TeachingMode.CORRECT if final else TeachingMode.HINT,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.SHORT if not final else ResponseLength.MEDIUM,
        strategy=(
            "They asked for a hint, so this is not a wrong answer. "
            + _ladder_rung(level)
            + (" Then wait." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.HINT_REQUEST.value,
        hint_level=level,
    )


_PRACTICE_BUILDERS: dict[AnswerEvaluation, _PracticeBuilder] = {
    AnswerEvaluation.CORRECT: _correct,
    AnswerEvaluation.PARTIALLY_CORRECT: _partially_correct,
    AnswerEvaluation.INCORRECT: _incorrect,
    AnswerEvaluation.NEEDS_HINT: _needs_hint,
    AnswerEvaluation.HINT_REQUEST: _hint_request,
}


class ConversationPolicy:
    """Maps intent + compact tutor state to a teaching move.

    Does not generate the spoken reply. The main LLM still does that.
    """

    def __init__(self) -> None:
        self._handlers: dict[StudentIntent, _Handler] = {
            StudentIntent.GREETING: self._greet,
            StudentIntent.UNRELATED: self._redirect,
            StudentIntent.RELATED_EDUCATIONAL: self._related,
            StudentIntent.HINT: self._hint,
            StudentIntent.ANSWER_REQUEST: self._answer_request,
            StudentIntent.CONFUSION: self._confusion,
            StudentIntent.REPEAT: self._repeat,
            StudentIntent.WHY_HOW: self._why_how,
            StudentIntent.STUDENT_ANSWER: self._student_answer,
            StudentIntent.PRACTICE_REQUEST: self._practice,
            StudentIntent.DISAGREEMENT: self._disagree,
            StudentIntent.ACKNOWLEDGEMENT: self._ack,
            StudentIntent.HESITATION: self._hesitate,
            StudentIntent.SUCCESS: self._success,
            StudentIntent.DEPTH_MORE: self._depth_more,
            StudentIntent.DEPTH_SHORT: self._depth_short,
            StudentIntent.DEPTH_SIMPLER: self._depth_simpler,
            StudentIntent.DISENGAGEMENT: self._disengage,
            StudentIntent.TOPIC_CHANGE: self._topic_change,
            StudentIntent.EXPLANATION: self._explain,
            StudentIntent.CLARIFICATION: self._explain,
        }

    def select(
        self,
        intent: StudentIntent,
        *,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None = None,
        practice: PracticeSnapshot | None = None,
        faq: FAQEntry | None = None,
    ) -> TutorDecision:
        if faq is not None:
            return self._apply_depth(self._faq(faq), state)
        if practice is not None and phase == "practice":
            adaptive = self._adaptive_practice(intent, practice)
            if adaptive is not None:
                return self._apply_depth(adaptive, state)
        handler = self._handlers.get(intent, self._default)
        decision = handler(intent, phase, state, utterance, tutor_context)
        return self._apply_depth(decision, state)

    def _adaptive_practice(
        self,
        intent: StudentIntent,
        practice: PracticeSnapshot,
    ) -> TutorDecision | None:
        """Teaching move for a scored practice turn. None = fall back to the generic path."""
        evaluation = practice.evaluation
        if evaluation is None:
            return None
        builder = _PRACTICE_BUILDERS.get(evaluation)
        if builder is None:
            return None
        return builder(intent, practice)

    def _faq(self, entry: FAQEntry) -> TutorDecision:
        return TutorDecision(
            intent=StudentIntent.FAQ,
            mode=TeachingMode.LEARN,
            move=ConversationMove.ANSWER_DIRECT,
            response_length=ResponseLength.SHORT,
            strategy=(
                "They asked a product FAQ, not a lesson question. Speak the FAQ "
                "answer in the student's language, teacher-like and concise. "
                "You may paraphrase, but do not add capabilities, subjects, "
                "classes, or tools that are not in the FAQ. Do not mention "
                "accounts, payments, banking, or customer support. Do not teach "
                "the current slide this turn."
            ),
            check_understanding=False,
            notes=("faq_knowledge",),
            faq_id=entry.id,
            faq_answer=entry.answer,
        )

    def _greet(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.GREET,
            move=ConversationMove.ACKNOWLEDGE,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Greet briefly and name the current topic if you know it. "
                "Do not launch into a lesson. Wait for them."
            ),
            check_understanding=False,
        )

    def _redirect(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        topic = state.topic_title or state.topic_id or "the maths you're working on"
        n = state.off_topic_count
        if n <= 0:
            sample = (
                f"That's outside our lesson for now. Let's stick with maths — "
                f"want to continue with {topic}?"
            )
        elif n == 1:
            sample = (
                "I get you, but I'm your maths tutor here. I can't switch into "
                "that kind of chat, but we can continue once you're ready."
            )
        else:
            sample = (
                "I can't switch into cricket or any other off-topic chat, but I can "
                f"help you with {topic}."
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.REDIRECT,
            move=ConversationMove.REDIRECT,
            response_length=ResponseLength.MICRO,
            strategy=(
                f"APPLICATION DOMAIN is {APPLICATION_DOMAIN} ({APPLICATION_SUBJECT}). "
                "This is a hard product rule, not optional. "
                "The student asked something completely unrelated. "
                "Acknowledge briefly and warmly, then redirect. "
                "Do NOT answer the unrelated topic. "
                "Do NOT become a general-purpose assistant. "
                "Do NOT agree to cricket, sports, news, politics, entertainment, "
                "weather, trivia, or any other off-topic chat — even if they insist. "
                "Do NOT pause tutoring or offer to talk about it later as if you will. "
                "Never say yes to switching domains. Never say things like "
                "'Sure, cricket chat it is'. "
                f"Vary the wording; a natural tone is like: {sample} "
                "Stay friendly, not authoritarian. Do not repeat the exact same sentence."
            ),
            check_understanding=False,
            notes=("scope_lock",),
        )

    def _related(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.LEARN,
            move=ConversationMove.EXPLAIN,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Related educational question — still inside Class 10 mathematics. "
                "Answer naturally in a couple of spoken sentences, then reconnect "
                "to the current lesson. Do not drift into unrelated chat."
            ),
            check_understanding=False,
        )

    def _hint(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.HINT,
            move=ConversationMove.HINT,
            response_length=ResponseLength.SHORT,
            strategy="Give only the next progressive hint. Do not give the full solution. Then wait.",
            use_next_hint=True,
            allow_reveal_answer=False,
            check_understanding=False,
        )

    def _answer_request(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.EVALUATE if phase == "practice" else TeachingMode.LEARN,
            move=ConversationMove.ANSWER_DIRECT,
            response_length=ResponseLength.SHORT,
            strategy="They asked for the answer explicitly — give a clear spoken answer, then a one-line why.",
            allow_reveal_answer=True,
            check_understanding=False,
        )

    def _confusion(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        focus = state.last_confusion_focus or "the idea you just explained"
        if state.confusion_streak >= 2:
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.CLARIFY,
                move=ConversationMove.ANALOGY,
                response_length=ResponseLength.MEDIUM,
                strategy=(
                    f"They are still stuck on {focus}. Change strategy: use a simple analogy, "
                    "not the same explanation again. Then one tiny check question."
                ),
                check_understanding=True,
            )
        if state.confusion_streak >= 1:
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.CLARIFY,
                move=ConversationMove.GIVE_EXAMPLE,
                response_length=ResponseLength.MEDIUM,
                strategy=(
                    f"They still don't get {focus}. Use a concrete number example. "
                    "Do not repeat the previous wording. No extra follow-up unless it is one short offer."
                ),
                check_understanding=False,
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.SIMPLIFY,
            response_length=ResponseLength.SHORT,
            strategy=(
                "They don't understand. Identify the likely confusing bit, simplify it, "
                "and do not repeat the previous answer. No automatic 'does that make sense?'."
            ),
            check_understanding=False,
        )

    def _repeat(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.REPEAT,
            move=ConversationMove.REPEAT,
            response_length=ResponseLength.SHORT,
            strategy="Rephrase the last useful idea more briefly and differently. Do not restart a long lecture.",
            check_understanding=False,
        )

    def _why_how(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        interrupt = is_interrupt_style(utterance)
        focus = (
            f" They were recently confused about: {state.last_confusion_focus}."
            if state.last_confusion_focus
            else ""
        )
        recovery = (
            " They interrupted — answer only this new question. "
            "Do not continue the previous explanation. Do not say 'as I was saying'."
            if interrupt
            else ""
        )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.ANSWER_DIRECT,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Answer the why/how using the visible section. Keep it concrete and short. "
                "Do not over-teach neighbouring ideas."
                f"{focus}{recovery}"
            ),
            check_understanding=False,
            notes=("interruption_recovery",) if interrupt else (),
        )

    def _student_answer(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if phase != "practice":
            return self._default(intent, phase, state, utterance, tutor_context)
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.EVALUATE,
            move=ConversationMove.EVALUATE,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Evaluate their attempt against the tutor-only expected answer. "
                "If correct, confirm briefly — do not launch a new lecture. "
                "If close, say so naturally ('Almost.', 'You're close.') and point at the specific slip. "
                "If wrong, do not say 'Incorrect.' Identify the likely mistake and ask at most one guiding question. "
                "Do not repeat the entire solution."
            ),
            allow_reveal_answer=False,
            check_understanding=False,
            notes=("Prefer Socratic follow-up over dumping the full solution.",),
        )

    def _practice(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if phase == "practice":
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.SOCRATIC,
                move=ConversationMove.GUIDE,
                response_length=ResponseLength.GUIDED,
                strategy=(
                    "They want to work the current practice item. Guide with one small "
                    "Socratic step. Do not reveal the full solution yet. Then wait."
                ),
                allow_reveal_answer=False,
                check_understanding=False,
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.PRACTICE,
            move=ConversationMove.GUIDE,
            response_length=ResponseLength.SHORT,
            strategy="Encourage them to use Next on screen for practice, or preview what practice will feel like briefly.",
            check_understanding=False,
        )

    def _disagree(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CORRECT,
            move=ConversationMove.CORRECT,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Take their objection seriously. Check against the lesson content. "
                "If they are right, say so. If not, correct the specific point gently — no 'Incorrect.'"
            ),
            check_understanding=False,
        )

    def _ack(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.ACKNOWLEDGE,
            move=ConversationMove.ACKNOWLEDGE,
            response_length=ResponseLength.MICRO,
            strategy=(
                "Short acknowledgement only — a beat like 'Yeah.' or 'Okay.' "
                "Do not explain more. Do not ask a question. Do not offer the next section. Wait."
            ),
            check_understanding=False,
        )

    def _hesitate(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.ACKNOWLEDGE,
            move=ConversationMove.WAIT,
            response_length=ResponseLength.MICRO,
            strategy=(
                "They sound hesitant or unfinished. Invite them to continue in a few words "
                "('Go ahead.', 'Take your time.', 'Yeah?'). Do not lecture. Do not finish their thought for them."
            ),
            check_understanding=False,
        )

    def _success(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if phase == "practice" and "answer" in (utterance or "").lower():
            strategy = (
                "They think they have the answer. Confirm briefly and check it against the expected answer. "
                "Do not start a new explanation."
            )
            mode = TeachingMode.EVALUATE
            move = ConversationMove.EVALUATE
        else:
            strategy = (
                "They just got it. Confirm briefly ('Exactly.', 'Yep, you've got it.'). "
                "Do not launch another explanation. Do not ask three follow-ups. Wait, or one optional next step only if it feels natural."
            )
            mode = TeachingMode.ACKNOWLEDGE
            move = ConversationMove.CELEBRATE
        return TutorDecision(
            intent=intent,
            mode=mode,
            move=move,
            response_length=ResponseLength.MICRO,
            strategy=strategy,
            check_understanding=False,
        )

    def _depth_more(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.LEARN,
            move=ConversationMove.DEEPEN,
            response_length=ResponseLength.MEDIUM,
            strategy=(
                "They asked for more depth on the current idea. Go one layer deeper. "
                "Stay on the same concept. No new unrelated topics."
            ),
            check_understanding=False,
        )

    def _depth_short(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        already = "already know" in (utterance or "").lower() or "i know this" in (
            utterance or ""
        ).lower()
        if already:
            strategy = (
                "They already know this. Don't re-explain. Acknowledge and offer to move on — one short line."
            )
        else:
            strategy = "They want it short. Acknowledge and stay concise from here. One short sentence now."
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.ACKNOWLEDGE,
            move=ConversationMove.SHORTEN,
            response_length=ResponseLength.MICRO,
            strategy=strategy,
            check_understanding=False,
        )

    def _depth_simpler(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.GIVE_EXAMPLE,
            response_length=ResponseLength.MEDIUM,
            strategy=(
                "They want a simpler take. Use easier words and a concrete example. "
                "Do not repeat the previous explanation."
            ),
            check_understanding=False,
        )

    def _disengage(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if is_move_on_request(utterance):
            strategy = (
                "They want to leave this problem. Acknowledge the feeling in a few natural words "
                "('Yeah, we can skip this.'). Do NOT repeat the current question. Do NOT insist they "
                "finish this step. One short wrap-up of the idea is enough if it helps, then let them "
                "move on. No quiz. No 'you should first'. No 'what is the largest multiple?'"
            )
        else:
            strategy = (
                "They sound bored, frustrated, or uninterested — that feeling is the main signal. "
                "Acknowledge briefly and naturally ('Yeah, let's make this quick.'). Immediately switch "
                "style: shorter, faster, simpler, spoken. Land the current idea with a concise "
                "explanation or tiny example, including the result if they are stuck on this question. "
                "Do NOT ask the same question again. Do NOT use a Socratic quiz. Never use textbook "
                "lines like 'It looks like you might be overlooking...', 'You should first...', or "
                "'What is the largest multiple?'. Sound like a patient Class 10 teacher, not an answer key."
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.LEARN,
            move=ConversationMove.SHORTEN,
            response_length=ResponseLength.SHORT,
            strategy=strategy,
            allow_reveal_answer=True,
            check_understanding=False,
            notes=("engagement",),
        )

    def _topic_change(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.REDIRECT,
            move=ConversationMove.REDIRECT,
            response_length=ResponseLength.SHORT,
            strategy=(
                "They asked to change topic. Acknowledge and let them move on — do not force the "
                "current problem. Point them to the lesson UI if they need another chapter. "
                "Natural transition, not 'Now we will proceed'."
            ),
            check_understanding=False,
        )

    def _explain(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if is_simple_factual(utterance):
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.LEARN,
                move=ConversationMove.ANSWER_DIRECT,
                response_length=ResponseLength.SHORT,
                strategy=(
                    "Simple factual question. Answer in one short sentence. "
                    "Do not explain neighbouring concepts, standard form, or extra theory unless they asked."
                ),
                check_understanding=False,
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.LEARN,
            move=ConversationMove.EXPLAIN,
            response_length=ResponseLength.MEDIUM,
            strategy=(
                "Explain the thing they asked, using the current on-screen section for 'this'/'that'/'here'. "
                "Do not use Socratic questioning for a direct 'what does this mean' request. "
                "Do not over-teach. At most one optional follow-up, and usually none."
            ),
            check_understanding=False,
        )

    def _default(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if is_short_refusal(utterance):
            return TutorDecision(
                intent=StudentIntent.CLARIFICATION,
                mode=TeachingMode.LEARN,
                move=ConversationMove.ANSWER_DIRECT,
                response_length=ResponseLength.SHORT,
                strategy=(
                    f"They said no. Stay a {APPLICATION_DOMAIN}. "
                    "Do NOT pause tutoring, do NOT offer general conversation, "
                    "do NOT switch domains, and do NOT treat 'no' as leaving maths. "
                    "Interpret it from the last maths turn — they may not want another "
                    "example, may not understand yet, or may want a different approach. "
                    "Invite them to continue with the current lesson in one short, natural line."
                ),
                check_understanding=False,
                notes=("contextual_no",),
            )
        resolved = intent if intent != StudentIntent.UNKNOWN else StudentIntent.EXPLANATION
        if phase == "practice":
            return TutorDecision(
                intent=resolved,
                mode=TeachingMode.SOCRATIC,
                move=ConversationMove.GUIDE,
                response_length=ResponseLength.GUIDED,
                strategy=(
                    "Guide them through the current practice question with one small step or question. "
                    "Do not reveal the full solution yet. Then wait."
                ),
                allow_reveal_answer=False,
                check_understanding=False,
            )
        return TutorDecision(
            intent=resolved,
            mode=TeachingMode.LEARN,
            move=ConversationMove.EXPLAIN,
            response_length=ResponseLength.SHORT,
            strategy=(
                "Respond using the current on-screen section in natural spoken language. "
                "Keep it short. Answer only what they need."
            ),
            check_understanding=False,
        )

    def _apply_depth(self, decision: TutorDecision, state: TutorState) -> TutorDecision:
        if decision.intent == StudentIntent.FAQ:
            return decision
        pref = state.depth_preference
        if decision.response_length == ResponseLength.MICRO:
            return decision
        extra: list[str] = list(decision.notes)
        length = decision.response_length
        if pref == "short" and length in {ResponseLength.MEDIUM, ResponseLength.GUIDED}:
            length = ResponseLength.SHORT
            extra.append("They asked to keep it short.")
        elif pref == "deep" and length == ResponseLength.SHORT and decision.move in {
            ConversationMove.EXPLAIN,
            ConversationMove.DEEPEN,
            ConversationMove.SIMPLIFY,
        }:
            length = ResponseLength.MEDIUM
            extra.append("They asked for more depth earlier.")
        elif pref == "beginner":
            extra.append("Explain like a beginner — simpler words, one idea at a time.")
        if extra == list(decision.notes) and length == decision.response_length:
            return decision
        return TutorDecision(
            intent=decision.intent,
            mode=decision.mode,
            strategy=decision.strategy,
            move=decision.move,
            response_length=length,
            allow_reveal_answer=decision.allow_reveal_answer,
            use_next_hint=decision.use_next_hint,
            check_understanding=decision.check_understanding,
            notes=tuple(extra),
            evaluation=decision.evaluation,
            hint_level=decision.hint_level,
            faq_id=decision.faq_id,
            faq_answer=decision.faq_answer,
        )
