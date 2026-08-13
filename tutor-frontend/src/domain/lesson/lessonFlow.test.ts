import { describe, expect, it } from "vitest";

import {
  buildLessonUnits,
  buildStudentVisibleLearningContext,
  buildTutorOnlyLearningContext,
  createInitialLessonState,
  getLessonSnapshot,
  goToNextLessonState,
  goToPreviousLessonState,
  learningContextFingerprint,
  toLearningContextPayload,
} from "@/domain/lesson/lessonFlow";
import { curriculumService } from "@/services/curriculum/CurriculumService";

const topic = curriculumService.getTopic("quadratic-formula");
if (!topic) {
  throw new Error("quadratic-formula topic missing");
}
const session = curriculumService.createSessionContext(topic.id);

describe("lesson flow", () => {
  it("starts on the first learning section", () => {
    const state = createInitialLessonState(topic.id);
    const snapshot = getLessonSnapshot(topic, state);
    expect(snapshot.state.phase).toBe("learning");
    expect(snapshot.state.currentSectionIndex).toBe(0);
    expect(snapshot.currentUnit).not.toBeNull();
    expect(snapshot.sectionProgress?.current).toBe(1);
    expect(snapshot.canGoPrevious).toBe(false);
  });

  it("advances through sections with next", () => {
    let state = createInitialLessonState(topic.id);
    const first = getLessonSnapshot(topic, state).currentUnit?.id;
    state = goToNextLessonState(topic, state);
    const second = getLessonSnapshot(topic, state).currentUnit?.id;
    expect(second).not.toBe(first);
    expect(state.currentSectionIndex).toBe(1);
  });

  it("goes back with previous", () => {
    let state = createInitialLessonState(topic.id);
    state = goToNextLessonState(topic, state);
    state = goToPreviousLessonState(topic, state);
    expect(state.phase).toBe("learning");
    expect(state.currentSectionIndex).toBe(0);
  });

  it("transitions from final section to practice", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    expect(state.phase).toBe("practice");
    expect(state.currentQuestionIndex).toBe(0);
    const snapshot = getLessonSnapshot(topic, state);
    expect(snapshot.currentQuestion?.id).toBe(topic.practiceQuestions[0]?.id);
  });

  it("advances practice questions and completes", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    expect(state.phase).toBe("practice");

    for (let i = 0; i < topic.practiceQuestions.length - 1; i++) {
      state = goToNextLessonState(topic, state);
      expect(state.phase).toBe("practice");
      expect(state.currentQuestionIndex).toBe(i + 1);
    }

    state = goToNextLessonState(topic, state);
    expect(state.phase).toBe("completed");
  });

  it("returns from first practice question to last learning section", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    state = goToPreviousLessonState(topic, state);
    expect(state.phase).toBe("learning");
    expect(state.currentSectionIndex).toBe(units.length - 1);
  });

  it("is a no-op next when already completed", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length + topic.practiceQuestions.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    expect(state.phase).toBe("completed");
    const again = goToNextLessonState(topic, state);
    expect(again).toEqual(state);
  });
});

describe("adaptive practice order", () => {
  const enterPractice = () => {
    let state = createInitialLessonState(topic.id);
    for (let i = 0; i < buildLessonUnits(topic).length; i++) {
      state = goToNextLessonState(topic, state);
    }
    return state;
  };

  it("keeps curriculum order when the tutor has no recommendation", () => {
    let state = enterPractice();
    state = goToNextLessonState(topic, state);
    expect(state.currentQuestionIndex).toBe(1);
  });

  it("jumps to the recommended difficulty instead of the next index", () => {
    const state = goToNextLessonState(topic, enterPractice(), {
      targetDifficulty: "hard",
    });
    const question = getLessonSnapshot(topic, state).currentQuestion;
    expect(question?.difficulty).toBe("hard");
  });

  it("never shows the same question twice", () => {
    let state = enterPractice();
    const seen = new Set<string>();
    for (let i = 0; i < topic.practiceQuestions.length; i++) {
      const current = getLessonSnapshot(topic, state).currentQuestion;
      if (current) {
        expect(seen.has(current.id)).toBe(false);
        seen.add(current.id);
      }
      state = goToNextLessonState(topic, state, { targetDifficulty: "medium" });
    }
    expect(state.phase).toBe("completed");
  });

  it("steps back along the path the student actually took", () => {
    let state = goToNextLessonState(topic, enterPractice(), {
      targetDifficulty: "hard",
    });
    const visitedId = getLessonSnapshot(topic, state).currentQuestion?.id;
    state = goToPreviousLessonState(topic, state);
    const back = getLessonSnapshot(topic, state).currentQuestion;
    expect(back?.id).toBe(topic.practiceQuestions[0]?.id);
    expect(back?.id).not.toBe(visitedId);
  });
});

describe("active learning context", () => {
  it("builds student-visible section context without solutions", () => {
    const state = createInitialLessonState(topic.id);
    const snapshot = getLessonSnapshot(topic, state);
    const visible = buildStudentVisibleLearningContext({
      session,
      topic,
      snapshot,
    });
    const payload = toLearningContextPayload(visible);
    expect(payload.phase).toBe("learning");
    expect(payload.sectionId).toBeTruthy();
    expect(payload).not.toHaveProperty("solution");
    expect(payload).not.toHaveProperty("expectedAnswer");
    expect(JSON.stringify(payload)).not.toContain('"solution"');
  });

  it("updates fingerprint when section changes", () => {
    let state = createInitialLessonState(topic.id);
    const a = learningContextFingerprint(
      buildStudentVisibleLearningContext({
        session,
        topic,
        snapshot: getLessonSnapshot(topic, state),
      }),
    );
    state = goToNextLessonState(topic, state);
    const b = learningContextFingerprint(
      buildStudentVisibleLearningContext({
        session,
        topic,
        snapshot: getLessonSnapshot(topic, state),
      }),
    );
    expect(a).not.toBe(b);
  });

  it("builds practice context without solution fields", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    const snapshot = getLessonSnapshot(topic, state);
    const visible = buildStudentVisibleLearningContext({
      session,
      topic,
      snapshot,
    });
    expect(visible.phase).toBe("practice");
    expect(visible.questionId).toBeTruthy();
    expect(visible.question).toBeTruthy();
    expect(visible).not.toHaveProperty("solution");
    expect(visible).not.toHaveProperty("expectedAnswer");
    expect(visible.hintCount).toBeGreaterThan(0);

    const tutorOnly = buildTutorOnlyLearningContext({ topic, snapshot });
    expect(tutorOnly.solution?.length).toBeGreaterThan(0);
    expect(tutorOnly.expectedAnswer).toBeTruthy();
  });

  it("updates fingerprint when question changes", () => {
    let state = createInitialLessonState(topic.id);
    const units = buildLessonUnits(topic);
    for (let i = 0; i < units.length; i++) {
      state = goToNextLessonState(topic, state);
    }
    const a = learningContextFingerprint(
      buildStudentVisibleLearningContext({
        session,
        topic,
        snapshot: getLessonSnapshot(topic, state),
      }),
    );
    state = goToNextLessonState(topic, state);
    const b = learningContextFingerprint(
      buildStudentVisibleLearningContext({
        session,
        topic,
        snapshot: getLessonSnapshot(topic, state),
      }),
    );
    expect(a).not.toBe(b);
  });
});
