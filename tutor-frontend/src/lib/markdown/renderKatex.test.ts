import { describe, expect, it } from "vitest";

import { renderKatex, resetKatexCache } from "@/lib/markdown/renderKatex";

describe("renderKatex", () => {
  it("returns the same HTML for the same formula", () => {
    resetKatexCache();
    const first = renderKatex("x^2", false);
    const second = renderKatex("x^2", false);
    expect(first).toBe(second);
    expect(first).toContain("katex");
  });

  it("does not treat inline and display as the same cache entry", () => {
    resetKatexCache();
    const inline = renderKatex("\\alpha + \\beta", false);
    const display = renderKatex("\\alpha + \\beta", true);
    expect(inline).not.toBe(display);
  });
});
