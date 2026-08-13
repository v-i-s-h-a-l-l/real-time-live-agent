"use client";

import { memo, useMemo } from "react";

import { renderKatex } from "@/lib/markdown/renderKatex";
import {
  parseTutorMarkdown,
  type BlockNode,
  type InlineNode,
} from "@/lib/markdown/tutorMarkdown";

import "katex/dist/katex.min.css";

function InlineView({ nodes }: { nodes: InlineNode[] }) {
  return (
    <>
      {nodes.map((node, index) => {
        if (node.type === "text") {
          return <span key={index}>{node.value}</span>;
        }
        if (node.type === "code") {
          return <code key={index}>{node.value}</code>;
        }
        if (node.type === "strong") {
          return (
            <strong key={index}>
              <InlineView nodes={node.children} />
            </strong>
          );
        }
        if (node.type === "em") {
          return (
            <em key={index}>
              <InlineView nodes={node.children} />
            </em>
          );
        }
        const html = renderKatex(node.value, false);
        if (!html) {
          return <code key={index}>{node.value}</code>;
        }
        return (
          <span
            key={index}
            className="tutor-math tutor-math-inline"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </>
  );
}

function BlockView({ block, index }: { block: BlockNode; index: number }) {
  if (block.type === "display-math") {
    const html = renderKatex(block.value, true);
    if (!html) {
      return (
        <pre key={index} className="tutor-math-fallback">
          {block.value}
        </pre>
      );
    }
    return (
      <div
        key={index}
        className="tutor-math tutor-math-display"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }
  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    return (
      <ListTag key={index} className="tutor-md-list">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>
            <InlineView nodes={item} />
          </li>
        ))}
      </ListTag>
    );
  }
  return (
    <p key={index}>
      <InlineView nodes={block.children} />
    </p>
  );
}

export const TutorMarkdown = memo(function TutorMarkdown({
  content,
}: {
  content: string;
}) {
  const blocks = useMemo(() => parseTutorMarkdown(content), [content]);
  if (!content.trim()) {
    return <p className="tutor-md-pending">Thinking…</p>;
  }
  return (
    <div className="tutor-md">
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} index={index} />
      ))}
    </div>
  );
});
