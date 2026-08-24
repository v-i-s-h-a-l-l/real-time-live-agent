"""Intent-handler routing (greet, explain, hint, disengage, …).

Moved out of policy.py with no logic changes. DEPTH_* intent handlers live
here — they choose a teaching move. Session depth overlay stays in depth.py.
PRACTICE_REQUEST is routing; scored-turn builders stay in policy_practice.py.
"""

from __future__ import annotations

from typing import Any

from tutor.intent import (
    is_interrupt_style,
    is_move_on_request,
    is_simple_factual,
    is_strong_ready,
    is_transition_confirm,
)
from tutor.policy_common import _continue_lesson, _steer
from tutor.scope import APPLICATION_DOMAIN, is_short_refusal
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
    TutorState,
)


class IntentRouter:
    def _greet(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if state.student_turns > 0:
            strategy = (
                "They said hello or made small talk mid-session. "
                "Do NOT introduce yourself as Lumina and do not restate the slide. "
                "One short warm reply. If they asked how you are, answer in one "
                "sentence and go straight back to the lesson — do not ask how they are."
            )
        else:
            strategy = (
                "Greet briefly and name the current topic if you know it. "
                "Do not launch into a lesson. Wait for them."
            )
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.GREET,
            move=ConversationMove.ACKNOWLEDGE,
            response_length=ResponseLength.SHORT,
            strategy=strategy,
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
        del phase, tutor_context
        return _steer(intent, state, utterance, topic_shift=False)

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
                "and do not repeat the previous answer. No reflexive comprehension check."
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
            "Do not continue the previous explanation, and do not narrate that you are resuming it."
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
        if is_transition_confirm(utterance) or is_strong_ready(utterance):
            return _continue_lesson(intent, phase=phase)
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
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.LEARN,
                move=ConversationMove.SHORTEN,
                response_length=ResponseLength.SHORT,
                strategy=(
                    "They want to leave this problem. Acknowledge the feeling in a few natural words "
                    "of your own. Do NOT repeat the current question. Do NOT insist they "
                    "finish this step. One short wrap-up of the idea is enough if it helps, then let them "
                    "move on. No quiz, no answer-key phrasing, no textbook instruction lines."
                ),
                allow_reveal_answer=True,
                check_understanding=False,
                notes=("engagement",),
            )
        # Boredom is a signal to change HOW you teach, not to shorten the same
        # definition and not to leave the topic. Switch method: example, analogy,
        # or a quick challenge on the SAME concept.
        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.GIVE_EXAMPLE,
            response_length=ResponseLength.MEDIUM,
            strategy=(
                "They sound bored or checked out. That feeling is a signal to change HOW you "
                "teach — NOT to shorten the same definition, and NOT to leave the topic. "
                "Grant the feeling in a few plain words of your own, then drop the formal "
                "wording and teach the SAME concept a different way: "
                "LEAD with ONE concrete worked example using small real numbers, or a "
                "real-world analogy, or why this actually matters, or one step you hand them "
                "to try. Actually deliver that example in this reply — it IS the reply, not a "
                "promise of one. "
                "Do NOT read the on-screen definition back. Do NOT restate, compress, or "
                "re-word the definition — brevity is not the fix, a different angle is. "
                "Announcing that you will keep it brief and then repeating the definition is "
                "the failure this is meant to prevent. "
                "Do NOT re-ask the same question. Do NOT offer to stop or pause, and do not "
                "invite them to return later — boredom is not a break request, so stay in "
                "the lesson and carry them through it. "
                "Use no textbook or answer-key phrasing, and no quiz-style prompts. "
                "Sound like a patient Class 10 teacher making the topic click."
            ),
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
        del phase, tutor_context
        return _steer(intent, state, utterance, topic_shift=True)

    def _explain(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
    ) -> TutorDecision:
        if is_transition_confirm(utterance) or is_strong_ready(utterance):
            return _continue_lesson(intent, phase=phase)
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
