"use client";

import { useCallback, useMemo, useState } from "react";

import type { Difficulty, Topic } from "@/domain/curriculum/types";
import {
  createInitialLessonState,
  getLessonSnapshot,
  goToNextLessonState,
  goToPreviousLessonState,
  type LessonSnapshot,
  type LessonState,
} from "@/domain/lesson/lessonFlow";

export interface UseLessonFlowResult {
  state: LessonState;
  snapshot: LessonSnapshot;
  goNext: () => void;
  goPrevious: () => void;
  restart: () => void;
}

/**
 * @param targetDifficulty Difficulty the tutor recommends next, from live practice
 * state. Undefined keeps the plain curriculum order (no session, or no attempts yet).
 */
export function useLessonFlow(
  topic: Topic,
  targetDifficulty?: Difficulty,
): UseLessonFlowResult {
  const [state, setState] = useState<LessonState>(() =>
    createInitialLessonState(topic.id),
  );

  const snapshot = useMemo(() => getLessonSnapshot(topic, state), [topic, state]);

  const goNext = useCallback(() => {
    setState((prev) => goToNextLessonState(topic, prev, { targetDifficulty }));
  }, [topic, targetDifficulty]);

  const goPrevious = useCallback(() => {
    setState((prev) => goToPreviousLessonState(topic, prev));
  }, [topic]);

  const restart = useCallback(() => {
    setState(createInitialLessonState(topic.id));
  }, [topic.id]);

  return {
    state: snapshot.state,
    snapshot,
    goNext,
    goPrevious,
    restart,
  };
}
