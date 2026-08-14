import { describe, expect, it } from "vitest";

import {
  emptyTranscript,
  isNearBottom,
  reduceTranscript,
  resolveScrollIntent,
} from "@/lib/voice/conversation";
import { ServerEvent, TEXT_INPUT_USER_ID } from "@/lib/voice/protocol";
import {
  containsUnsafeHtml,
  parseTutorMarkdown,
} from "@/lib/markdown/tutorMarkdown";
import { VoiceAgentClient } from "@/lib/voice/VoiceAgentClient";

describe("transcript reducer", () => {
  it("adds a voice user transcript", () => {
    const next = reduceTranscript(emptyTranscript(), {
      type: "user-echo",
      content: "Explain this slide.",
    });
    expect(next.messages).toHaveLength(1);
    expect(next.messages[0]?.role).toBe("user");
    expect(next.messages[0]?.source).toBe("voice");
    expect(next.messages[0]?.content).toBe("Explain this slide.");
  });

  it("streams assistant tokens into a single message", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "assistant-start",
      id: "a1",
    });
    state = reduceTranscript(state, { type: "assistant-delta", delta: "Sure. " });
    state = reduceTranscript(state, {
      type: "assistant-delta",
      delta: "Euclid's Division Lemma",
    });
    state = reduceTranscript(state, { type: "assistant-end" });
    const assistants = state.messages.filter((m) => m.role === "assistant");
    expect(assistants).toHaveLength(1);
    expect(assistants[0]?.content).toBe("Sure. Euclid's Division Lemma");
    expect(assistants[0]?.status).toBe("complete");
    expect(state.streamingId).toBeNull();
  });

  it("keeps a typed user message once and ignores the text echo", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "user",
      id: "u1",
      content: "Explain this in simpler terms.",
      source: "text",
    });
    state = reduceTranscript(state, {
      type: "user-echo",
      content: "Explain this in simpler terms.",
      userId: TEXT_INPUT_USER_ID,
    });
    expect(state.messages.filter((m) => m.role === "user")).toHaveLength(1);
  });

  it("shares one conversation across typed and voice turns", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "user-echo",
      content: "What is Euclid's Division Lemma?",
    });
    state = reduceTranscript(state, { type: "assistant-start", id: "a1" });
    state = reduceTranscript(state, {
      type: "assistant-delta",
      delta: "It states that...",
    });
    state = reduceTranscript(state, { type: "assistant-end" });
    state = reduceTranscript(state, {
      type: "user",
      id: "u2",
      content: "Can you explain the second part?",
      source: "text",
    });
    expect(state.messages.map((m) => m.role)).toEqual([
      "user",
      "assistant",
      "user",
    ]);
  });

  it("does not duplicate messages after a reconnect reset", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "user-echo",
      content: "Hello",
    });
    state = reduceTranscript(state, { type: "reset" });
    state = reduceTranscript(state, { type: "user-echo", content: "Hello" });
    expect(state.messages).toHaveLength(1);
  });

  it("marks a streaming reply as an error without adding a second bubble", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "assistant-start",
      id: "a1",
    });
    state = reduceTranscript(state, { type: "assistant-delta", delta: "Almost." });
    state = reduceTranscript(state, {
      type: "assistant-error",
      message: "The tutor did not return a reply. Try again.",
    });
    expect(state.streamingId).toBeNull();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.status).toBe("error");
    expect(state.messages[0]?.content).toBe(
      "The tutor did not return a reply. Try again.",
    );
  });

  it("appends a complete break acknowledgement without streaming tokens", () => {
    let state = reduceTranscript(emptyTranscript(), {
      type: "user-echo",
      content: "I need a two-minute break.",
    });
    state = reduceTranscript(state, {
      type: "assistant-complete",
      id: "b1",
      content: "Sure, take a two-minute break. I'll let you know when it's over.",
    });
    expect(state.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(state.messages[1]?.content).toContain("two-minute break");
    expect(state.streamingId).toBeNull();
  });
});

describe("auto-scroll policy", () => {
  it("sticks to the bottom when already near it", () => {
    expect(isNearBottom(20)).toBe(true);
  });

  it("respects the student scrolling upward", () => {
    expect(isNearBottom(240)).toBe(false);
  });

  it("follows new messages while the student is at the bottom", () => {
    expect(
      resolveScrollIntent({
        arrived: 1,
        latestRole: "assistant",
        anchored: true,
      }),
    ).toBe("pin");
  });

  it("keeps the reading position when the student has scrolled up", () => {
    expect(
      resolveScrollIntent({
        arrived: 1,
        latestRole: "assistant",
        anchored: false,
      }),
    ).toBe("notify");
  });

  it("does not flag streaming tokens of an already counted message", () => {
    expect(
      resolveScrollIntent({
        arrived: 0,
        latestRole: "assistant",
        anchored: false,
      }),
    ).toBe("hold");
  });

  it("returns to the latest turn when the student sends a message", () => {
    expect(
      resolveScrollIntent({ arrived: 1, latestRole: "user", anchored: false }),
    ).toBe("pin");
  });
});

describe("tutor markdown + math", () => {
  it("parses display equations", () => {
    const blocks = parseTutorMarkdown(
      "Let's solve it.\n\n$$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$",
    );
    const math = blocks.find((b) => b.type === "display-math");
    expect(math && math.type === "display-math" && math.value).toContain(
      "\\frac{-b",
    );
  });

  it("parses LaTeX bracket display math without showing raw delimiters", () => {
    const blocks = parseTutorMarkdown(
      "we can write \\[ a = bq + r \\] where q is the quotient.",
    );
    const math = blocks.find((b) => b.type === "display-math");
    expect(math && math.type === "display-math" && math.value).toBe("a = bq + r");
    const joined = JSON.stringify(blocks);
    expect(joined).not.toContain("\\[");
    expect(joined).not.toContain("\\]");
  });

  it("parses inline inequalities as math, not stripped text", () => {
    const blocks = parseTutorMarkdown(
      "where q is the quotient, r is the remainder and $0 \\leq r < b$.",
    );
    expect(blocks[0]?.type).toBe("paragraph");
    if (blocks[0]?.type !== "paragraph") return;
    const math = blocks[0].children.find((n) => n.type === "math");
    expect(math && math.type === "math" && math.value).toBe("0 \\leq r < b");
  });

  it("parses inline math", () => {
    const blocks = parseTutorMarkdown("Here $a = 2$ and $b = 5$.");
    expect(blocks[0]?.type).toBe("paragraph");
    if (blocks[0]?.type !== "paragraph") return;
    const math = blocks[0].children.filter((n) => n.type === "math");
    expect(math).toHaveLength(2);
  });

  it("does not treat raw HTML as markup", () => {
    const blocks = parseTutorMarkdown("<script>alert(1)</script> and **bold**");
    expect(containsUnsafeHtml("<script>alert(1)</script>")).toBe(true);
    const paragraph = blocks.find((b) => b.type === "paragraph");
    expect(paragraph?.type).toBe("paragraph");
    if (paragraph?.type !== "paragraph") return;
    const text = paragraph.children
      .map((n) => (n.type === "text" ? n.value : n.type === "strong" ? "BOLD" : ""))
      .join("");
    expect(text).toContain("<script>alert(1)</script>");
    expect(text).toContain("BOLD");
  });

  it("keeps consecutive calculation steps on separate lines", () => {
    const blocks = parseTutorMarkdown(
      "Let's try 84 and 30:\n84 = 30 × 2 + 24\n30 = 24 × 1 + 6\n24 = 6 × 4 + 0\nso the HCF is 6.",
    );
    const paragraphs = blocks.filter((b) => b.type === "paragraph");
    expect(paragraphs.length).toBeGreaterThanOrEqual(5);
    const texts = paragraphs.map((b) =>
      b.type === "paragraph"
        ? b.children.map((n) => (n.type === "text" ? n.value : "")).join("")
        : "",
    );
    expect(texts.some((t) => t.includes("84 = 30"))).toBe(true);
    expect(texts.some((t) => t.includes("30 = 24"))).toBe(true);
    expect(texts.join(" ")).not.toMatch(/84 = 30 × 2 \+ 24, 30 = 24/);
  });

  it("keeps malformed math as text instead of crashing", () => {
    expect(() => parseTutorMarkdown("$$\\frac{1}{")).not.toThrow();
    const blocks = parseTutorMarkdown("Still going $$\\frac{1}{");
    expect(blocks.length).toBeGreaterThan(0);
  });
});

describe("VoiceAgentClient RTVI events", () => {
  it("forwards user transcription and streams one assistant callback sequence", () => {
    const users: string[] = [];
    const deltas: string[] = [];
    let ended = 0;
    const client = new VoiceAgentClient(
      { wsUrl: "ws://127.0.0.1:9/ws" },
      {
        onTranscription: (text) => users.push(text),
        onAssistantText: (delta) => deltas.push(delta),
        onAssistantTextEnd: () => {
          ended += 1;
        },
      },
    );

    client.handleServerEvent({
      type: ServerEvent.userTranscription,
      data: { text: "Explain this slide." },
    });
    client.handleServerEvent({ type: ServerEvent.botLlmStarted });
    client.handleServerEvent({
      type: ServerEvent.botLlmText,
      data: { text: "Sure. " },
    });
    client.handleServerEvent({
      type: ServerEvent.botLlmText,
      data: { text: "This slide explains Euclid." },
    });
    client.handleServerEvent({ type: ServerEvent.botLlmStopped });

    expect(users).toEqual(["Explain this slide."]);
    expect(deltas.join("")).toBe("Sure. This slide explains Euclid.");
    expect(ended).toBe(1);
  });

  it("forwards study-break events without touching the transcript callbacks", () => {
    const breaks: string[] = [];
    const deltas: string[] = [];
    const client = new VoiceAgentClient(
      { wsUrl: "ws://127.0.0.1:9/ws" },
      {
        onAssistantText: (delta) => deltas.push(delta),
        onBreakEvent: (event) => breaks.push(event.type),
      },
    );

    client.handleServerEvent({
      type: ServerEvent.breakStarted,
      data: {
        durationMinutes: 2,
        startedAt: 1000,
        endsAt: 121000,
        spoken: "Sure, take a two-minute break. I'll let you know when it's over.",
      },
    });
    client.handleServerEvent({ type: ServerEvent.breakEnded });

    expect(breaks).toEqual(["break_started", "break_ended"]);
    expect(deltas).toEqual([]);
  });

  it("forwards safety alerts without using the LLM transcript callbacks", () => {
    const alerts: Array<{ type: string; category?: string }> = [];
    const deltas: string[] = [];
    const client = new VoiceAgentClient(
      { wsUrl: "ws://127.0.0.1:9/ws" },
      {
        onAssistantText: (delta) => deltas.push(delta),
        onSafetyAlert: (event) =>
          alerts.push({ type: event.type, category: event.category }),
      },
    );

    client.handleServerEvent({
      type: ServerEvent.safetyAlert,
      data: {
        category: "self_harm",
        severity: "high",
        timestamp: 1_700_500,
        spoken: "I'm really sorry you're feeling this way.",
      },
    });

    expect(alerts).toEqual([{ type: "safety_alert", category: "self_harm" }]);
    expect(deltas).toEqual([]);
  });

  it("does not send text_input when the socket is closed", () => {
    const client = new VoiceAgentClient({ wsUrl: "ws://127.0.0.1:9/ws" });
    expect(client.sendTextInput("Hello")).toBe(false);
  });
});
