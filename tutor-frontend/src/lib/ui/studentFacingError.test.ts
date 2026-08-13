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
    expect(studentFacingError("Start voice to send a message.")).toBe(
      "Start voice to send a message.",
    );
  });
});
