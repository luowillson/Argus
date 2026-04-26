"use client";

import { InlineMath, BlockMath } from "react-katex";

type Segment =
  | { type: "text"; value: string }
  | { type: "inline"; value: string }
  | { type: "block"; value: string };

function parse(text: string): Segment[] {
  const segments: Segment[] = [];
  // Match $$...$$ (block) before $...$ (inline) to avoid greedily eating delimiters.
  const re = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({ type: "text", value: text.slice(cursor, match.index) });
    }
    if (match[1] !== undefined) {
      segments.push({ type: "block", value: match[1] });
    } else if (match[2] !== undefined) {
      segments.push({ type: "inline", value: match[2] });
    }
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    segments.push({ type: "text", value: text.slice(cursor) });
  }

  return segments;
}

export function LatexText({ children }: { children: string }) {
  if (!children) return null;

  const segments = parse(children);

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === "block") {
          return (
            <span key={i} className="my-2 block">
              <BlockMath math={seg.value} errorColor="#888" />
            </span>
          );
        }
        if (seg.type === "inline") {
          return <InlineMath key={i} math={seg.value} errorColor="#888" />;
        }
        return <span key={i}>{seg.value}</span>;
      })}
    </>
  );
}
