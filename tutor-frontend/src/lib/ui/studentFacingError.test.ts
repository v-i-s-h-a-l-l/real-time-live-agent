import { describe, expect, it } from "vitest";

import { studentFacingError } from "@/lib/ui/studentFacingError";

describe("studentFacingError", () => {
  it("hides protocol language", () => {
    expect(studentFacingError("WebSocket connection failed")).toBe(
      "Connection lost. Reconnecting…",
    );
    expect(studentFacingError("No microphone audio detected.")).toContain(
      "microphone",
    );
    expect(studentFacingError("boom")).toBe("Something went wrong. Try again.");
    expect(studentFacingError("Could not start a secure session.")).toBe(
      "Could not start a secure session.",
    );
    expect(studentFacingError("unauthorized 4401")).toBe(
      "Could not start a secure session.",
    );
    expect(studentFacingError("Please sign in to start a voice session.")).toBe(
      "Please sign in to start a voice session.",
    );
  });
});
