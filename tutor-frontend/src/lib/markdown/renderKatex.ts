/**
 * KaTeX HTML for tutor transcript math.
 *
 * Same options as before: untrusted TeX, HTML only, never throw.
 * Results are cached because a streaming reply re-typesets every already-closed
 * formula on each token, and the HTML does not change.
 */

import katex from "katex";

const KATEX_OPTIONS = {
  throwOnError: false,
  trust: false,
  strict: "ignore" as const,
  output: "html" as const,
};

const CACHE_LIMIT = 128;
const cache = new Map<string, string>();

export function renderKatex(tex: string, display: boolean): string {
  const key = `${display ? "d" : "i"}:${tex}`;
  const hit = cache.get(key);
  if (hit !== undefined) {
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }

  let html = "";
  try {
    html = katex.renderToString(tex, {
      ...KATEX_OPTIONS,
      displayMode: display,
    });
  } catch {
    html = "";
  }

  if (cache.size >= CACHE_LIMIT) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
  cache.set(key, html);
  return html;
}

/** Test helper — production code does not need to clear the cache. */
export function resetKatexCache(): void {
  cache.clear();
}
