/**
 * Safe educational markdown + math parser.
 *
 * LLM output is untrusted. This parser never produces HTML: it returns a node
 * tree whose text values are rendered as React children, so any markup in the
 * reply is displayed literally rather than interpreted. The only HTML in the
 * transcript comes from KaTeX, which runs with `trust: false` (see
 * TutorMarkdown). Keep it that way — do not add a raw-HTML node type.
 */

export type InlineNode =
  | { type: "text"; value: string }
  | { type: "math"; value: string }
  | { type: "strong"; children: InlineNode[] }
  | { type: "em"; children: InlineNode[] }
  | { type: "code"; value: string };

export type BlockNode =
  | { type: "paragraph"; children: InlineNode[] }
  | { type: "display-math"; value: string }
  | { type: "list"; ordered: boolean; items: InlineNode[][] };

const DISPLAY_MATH = /\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$/g;

function parseInline(text: string): InlineNode[] {
  const nodes: InlineNode[] = [];
  const pattern =
    /(\$\$[\s\S]+?\$\$)|(\\\[[\s\S]+?\\\])|(\\\([\s\S]+?\\\))|(\$[^$\n]+?\$)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push({ type: "text", value: text.slice(last, match.index) });
    }
    const token = match[0];
    if (token.startsWith("$$") && token.endsWith("$$")) {
      nodes.push({ type: "math", value: token.slice(2, -2).trim() });
    } else if (token.startsWith("\\[") && token.endsWith("\\]")) {
      nodes.push({ type: "math", value: token.slice(2, -2).trim() });
    } else if (token.startsWith("\\(") && token.endsWith("\\)")) {
      nodes.push({ type: "math", value: token.slice(2, -2).trim() });
    } else if (token.startsWith("$") && token.endsWith("$")) {
      nodes.push({ type: "math", value: token.slice(1, -1).trim() });
    } else if (token.startsWith("**")) {
      nodes.push({
        type: "strong",
        children: [{ type: "text", value: token.slice(2, -2) }],
      });
    } else if (token.startsWith("*")) {
      nodes.push({
        type: "em",
        children: [{ type: "text", value: token.slice(1, -1) }],
      });
    } else if (token.startsWith("`")) {
      nodes.push({ type: "code", value: token.slice(1, -1) });
    }
    last = match.index + token.length;
  }
  if (last < text.length) {
    nodes.push({ type: "text", value: text.slice(last) });
  }
  return nodes.length ? nodes : [{ type: "text", value: text }];
}

export function parseTutorMarkdown(content: string): BlockNode[] {
  const source = content.replace(/\r\n/g, "\n");
  const blocks: BlockNode[] = [];
  let cursor = 0;
  DISPLAY_MATH.lastIndex = 0;
  let match: RegExpExecArray | null;
  const segments: Array<{ math?: string; text?: string }> = [];

  while ((match = DISPLAY_MATH.exec(source)) !== null) {
    if (match.index > cursor) {
      segments.push({ text: source.slice(cursor, match.index) });
    }
    segments.push({ math: (match[1] ?? match[2] ?? "").trim() });
    cursor = match.index + match[0].length;
  }
  if (cursor < source.length) {
    segments.push({ text: source.slice(cursor) });
  }
  if (!segments.length) {
    segments.push({ text: source });
  }

  for (const segment of segments) {
    if (segment.math !== undefined) {
      blocks.push({ type: "display-math", value: segment.math });
      continue;
    }
    const text = (segment.text || "").trim();
    if (!text) continue;

    const lines = text.split("\n");
    let paragraph: string[] = [];
    let list: { ordered: boolean; items: string[] } | null = null;

    const flushParagraph = () => {
      if (!paragraph.length) return;
      blocks.push({
        type: "paragraph",
        children: parseInline(paragraph.join("\n").trim()),
      });
      paragraph = [];
    };
    const flushList = () => {
      if (!list) return;
      blocks.push({
        type: "list",
        ordered: list.ordered,
        items: list.items.map((item) => parseInline(item)),
      });
      list = null;
    };

    for (const line of lines) {
      const unordered = line.match(/^\s*[-*]\s+(.+)$/);
      const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
      if (unordered) {
        flushParagraph();
        if (!list || list.ordered) {
          flushList();
          list = { ordered: false, items: [] };
        }
        list.items.push(unordered[1]);
        continue;
      }
      if (ordered) {
        flushParagraph();
        if (!list || !list.ordered) {
          flushList();
          list = { ordered: true, items: [] };
        }
        list.items.push(ordered[1]);
        continue;
      }
      if (!line.trim()) {
        flushList();
        flushParagraph();
        continue;
      }
      flushList();
      flushParagraph();
      paragraph.push(line.trim());
      flushParagraph();
    }
    flushList();
    flushParagraph();
  }

  return blocks;
}

export function containsUnsafeHtml(content: string): boolean {
  return /<\s*(script|iframe|object|embed|link|meta|style)\b/i.test(content);
}
