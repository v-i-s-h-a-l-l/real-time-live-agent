import { describe, expect, it } from "vitest";

import { resolveVoiceConnectionNotice } from "@/components/lesson/VoiceConnectionBanner";

describe("resolveVoiceConnectionNotice", () => {
  it("shows nothing before the first connection", () => {
    expect(resolveVoiceConnectionNotice("connecting", true, false)).toBeNull();
    expect(resolveVoiceConnectionNotice("idle", false, false)).toBeNull();
  });

  it("shows reconnecting after a prior connection", () => {
    expect(resolveVoiceConnectionNotice("connecting", true, true)).toBe(
      "reconnecting",
    );
  });

  it("shows lost only after a prior connection failed", () => {
    expect(resolveVoiceConnectionNotice("error", true, true)).toBe("lost");
    expect(resolveVoiceConnectionNotice("error", true, false)).toBeNull();
  });

  it("does not claim loss while connected", () => {
    expect(resolveVoiceConnectionNotice("connected", true, true)).toBeNull();
  });
});
