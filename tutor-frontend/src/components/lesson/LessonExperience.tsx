"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { LessonNav } from "@/components/lesson/LessonNav";
import { LessonUnitView } from "@/components/lesson/LessonUnitView";
import { LessonVoiceDock } from "@/components/lesson/LessonVoiceDock";
import { SequentialPracticeCard } from "@/components/lesson/SequentialPracticeCard";
import type { Topic, TutorSessionContext } from "@/domain/curriculum/types";
import { useLearningContextSync } from "@/hooks/useLearningContextSync";
import { useLessonFlow } from "@/hooks/useLessonFlow";
import { useVoiceSession } from "@/hooks/useVoiceSession";
import { subjectPath } from "@/lib/routes";
import { DEFAULT_TUTOR_VOICE_ID } from "@/lib/voice/voices";

export function LessonExperience({
  topic,
  sessionContext,
}: {
  topic: Topic;
  sessionContext: TutorSessionContext;
}) {
  const {
    connectionState,
    turnState,
    micState,
    isActive,
    errorMessage,
    startSession,
    endSession,
    clearError,
    updateLearningContext,
    updateTutorContext,
    setTtsVoice,
    messages,
    sendText,
    voiceResponsesEnabled,
    setVoiceResponsesEnabled,
    studyBreak,
    safetyAlert,
    practiceProgress,
  } = useVoiceSession();

  // The tutor only recommends a difficulty once it has seen an attempt; until then
  // practice follows plain curriculum order.
  const attempts =
    practiceProgress.correct + practiceProgress.partial + practiceProgress.incorrect;
  const lesson = useLessonFlow(
    topic,
    attempts > 0 ? practiceProgress.recommendedDifficulty : undefined,
  );

  const [voiceId, setVoiceId] = useState(DEFAULT_TUTOR_VOICE_ID);
  const voiceReady = connectionState === "connected";
  const [practiceAttempted, setPracticeAttempted] = useState(false);

  const { snapshot } = lesson;
  const progressLabel =
    snapshot.state.phase === "learning" && snapshot.sectionProgress
      ? `${snapshot.sectionProgress.current} / ${snapshot.sectionProgress.total}`
      : snapshot.state.phase === "practice" && snapshot.questionProgress
        ? `Question ${snapshot.questionProgress.current} of ${snapshot.questionProgress.total}`
        : "Complete";

  useEffect(() => {
    setPracticeAttempted(false);
  }, [snapshot.state.currentQuestionIndex, snapshot.state.phase]);

  useLearningContextSync({
    topic,
    sessionContext,
    snapshot,
    voiceReady,
    onLearningContext: updateLearningContext,
    onTutorContext: updateTutorContext,
  });

  const nextDisabled =
    snapshot.state.phase === "practice" && !practiceAttempted;

  return (
    <div className="lesson-layout">
      <header className="lesson-header">
        <div className="lesson-header-copy">
          <p className="session-kicker">
            {sessionContext.subjectName} · {sessionContext.chapterTitle}
          </p>
          <h1 className="session-title">{sessionContext.topicTitle}</h1>
        </div>
        {snapshot.state.phase !== "completed" ? (
          <p className="lesson-progress-chip">{progressLabel}</p>
        ) : null}
      </header>

      <div className="lesson-body">
        <div className="lesson-main">
          {snapshot.state.phase === "learning" && snapshot.currentUnit ? (
            <LessonUnitView unit={snapshot.currentUnit} />
          ) : null}

          {snapshot.state.phase === "practice" && snapshot.currentQuestion ? (
            <SequentialPracticeCard
              key={snapshot.currentQuestion.id}
              question={snapshot.currentQuestion}
              progressLabel={progressLabel}
              onAttempted={setPracticeAttempted}
              onSubmitAnswer={voiceReady ? sendText : undefined}
              progress={practiceProgress}
            />
          ) : null}

          {snapshot.state.phase === "completed" ? (
            <div className="lesson-complete">
              <h2>Lesson complete</h2>
              <p>
                You finished the learning sequence and practice for{" "}
                {sessionContext.topicTitle}.
              </p>
              <div className="lesson-complete-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={lesson.restart}
                >
                  Restart lesson
                </button>
                <Link
                  href={subjectPath(sessionContext.subjectId)}
                  className="btn btn-ghost"
                >
                  Back to chapters
                </Link>
              </div>
            </div>
          ) : null}

          {snapshot.state.phase !== "completed" ? (
            <LessonNav
              progressLabel={progressLabel}
              canGoPrevious={snapshot.canGoPrevious}
              canGoNext={snapshot.canGoNext}
              nextLabel={snapshot.nextLabel}
              nextDisabled={nextDisabled}
              onPrevious={lesson.goPrevious}
              onNext={lesson.goNext}
            />
          ) : null}
        </div>

        <LessonVoiceDock
          lessonTitle={sessionContext.topicTitle}
          connectionState={connectionState}
          turnState={turnState}
          micState={micState}
          isActive={isActive}
          errorMessage={errorMessage}
          voiceId={voiceId}
          messages={messages}
          voiceResponsesEnabled={voiceResponsesEnabled}
          onVoiceResponsesChange={setVoiceResponsesEnabled}
          onSendText={sendText}
          onVoiceChange={(nextVoiceId) => {
            setVoiceId(nextVoiceId);
            setTtsVoice(nextVoiceId);
          }}
          onStart={() => {
            void startSession(sessionContext, voiceId);
          }}
          onEnd={endSession}
          onClearError={clearError}
          studyBreak={studyBreak}
          safetyAlert={safetyAlert}
        />
      </div>
    </div>
  );
}
