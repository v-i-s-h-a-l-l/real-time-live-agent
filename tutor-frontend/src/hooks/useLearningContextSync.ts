"use client";

import { useEffect, useRef } from "react";

import type { Topic, TutorSessionContext } from "@/domain/curriculum/types";
import {
  buildStudentVisibleLearningContext,
  buildTutorOnlyLearningContext,
  learningContextFingerprint,
  toLearningContextPayload,
  toTutorContextPayload,
  type LessonSnapshot,
} from "@/domain/lesson/lessonFlow";
import type { JsonObject } from "@/lib/voice/types";

/**
 * Pushes the on-screen unit to the voice engine.
 *
 * Two effects on purpose: one follows slide/question changes while the
 * socket is open; the other fires once when the socket becomes ready so
 * the first slide is not dropped during connect.
 */
export function useLearningContextSync({
  topic,
  sessionContext,
  snapshot,
  voiceReady,
  onLearningContext,
  onTutorContext,
}: {
  topic: Topic;
  sessionContext: TutorSessionContext;
  snapshot: LessonSnapshot;
  voiceReady: boolean;
  onLearningContext: (context: JsonObject) => void;
  onTutorContext: (context: JsonObject) => void;
}): void {
  const lastFingerprint = useRef<string | null>(null);
  const onLearningRef = useRef(onLearningContext);
  const onTutorRef = useRef(onTutorContext);
  onLearningRef.current = onLearningContext;
  onTutorRef.current = onTutorContext;

  const pushContexts = () => {
    const visible = buildStudentVisibleLearningContext({
      session: sessionContext,
      topic,
      snapshot,
    });
    const tutorOnly = buildTutorOnlyLearningContext({ topic, snapshot });
    if (process.env.NODE_ENV !== "production") {
      console.info("[ACTIVE_LEARNING_CONTEXT_UPDATED]", {
        topicId: visible.topicId,
        sectionId: visible.sectionId,
        sectionTitle: visible.sectionTitle,
        phase: visible.phase,
        questionId: visible.questionId,
      });
    }
    onLearningRef.current(toLearningContextPayload(visible));
    onTutorRef.current(toTutorContextPayload(tutorOnly));
  };

  useEffect(() => {
    const visible = buildStudentVisibleLearningContext({
      session: sessionContext,
      topic,
      snapshot,
    });
    const fingerprint = learningContextFingerprint(visible);
    if (lastFingerprint.current === fingerprint) return;
    lastFingerprint.current = fingerprint;

    if (voiceReady) {
      pushContexts();
    }
    // pushContexts closes over the latest snapshot via this effect's deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot, sessionContext, topic, voiceReady]);

  useEffect(() => {
    if (!voiceReady) {
      lastFingerprint.current = null;
      return;
    }
    const visible = buildStudentVisibleLearningContext({
      session: sessionContext,
      topic,
      snapshot,
    });
    lastFingerprint.current = learningContextFingerprint(visible);
    pushContexts();
    // First push after the socket opens; snapshot is read at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceReady]);
}
