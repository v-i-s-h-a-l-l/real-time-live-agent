"use client";

import { useEffect, useRef } from "react";

import type { Topic, TutorSessionContext } from "@/domain/curriculum/types";
import {
  buildStudentVisibleLearningContext,
  learningContextFingerprint,
  toLearningContextPayload,
  type LessonSnapshot,
} from "@/domain/lesson/lessonFlow";
import type { JsonObject } from "@/lib/voice/types";

/**
 * Pushes the on-screen unit to the voice engine.
 *
 * Two effects on purpose: one follows slide/question changes while the
 * socket is open; the other fires once when the socket becomes ready so
 * the first slide is not dropped during connect.
 *
 * Tutor-only answers are fetched from the Next.js server and HMAC-signed;
 * they are never read from the client lesson bundle.
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
  const snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;
  const topicRef = useRef(topic);
  topicRef.current = topic;
  const sessionRef = useRef(sessionContext);
  sessionRef.current = sessionContext;

  const pushContexts = (active: LessonSnapshot) => {
    const visible = buildStudentVisibleLearningContext({
      session: sessionRef.current,
      topic: topicRef.current,
      snapshot: active,
    });
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

    void fetch("/api/tutor-context", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topicId: topicRef.current.id,
        phase: active.state.phase,
        questionId: active.currentQuestion?.id ?? "",
      }),
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { context?: JsonObject } | null) => {
        if (data?.context && typeof data.context === "object") {
          onTutorRef.current(data.context);
        }
      })
      .catch(() => {
        // Visible learning context is enough for tutoring to continue.
      });
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
      pushContexts(snapshot);
    }
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
    pushContexts(snapshot);
  }, [voiceReady]);
}
