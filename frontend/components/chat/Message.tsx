"use client";

import { Fragment } from "react";
import { stripThinkTags } from "@/lib/api";

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

type MentorBlock =
  | { type: "paragraph"; lines: string[] }
  | { type: "table"; headers: string[]; rows: string[][] };

function cleanInline(value: string) {
  return value
    .replaceAll("`", "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function normalizeInlineText(value: string) {
  return cleanInline(value).trim();
}

function renderCellContent(value: string) {
  // Split on <br> variants so bullet lists inside table cells render on separate lines
  const segments = value.split(/<br\s*\/?>/i);
  if (segments.length === 1) return renderInlineText(value);
  return (
    <>
      {segments.map((seg, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {renderInlineText(seg)}
        </Fragment>
      ))}
    </>
  );
}

function parseInlineStrong(text: string) {
  const parts: Array<{ text: string; strong: boolean }> = [];
  const pattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match = pattern.exec(text);

  while (match) {
    if (match.index > lastIndex) {
      parts.push({ text: cleanInline(text.slice(lastIndex, match.index)), strong: false });
    }
    parts.push({ text: cleanInline(match[1]), strong: true });
    lastIndex = match.index + match[0].length;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    parts.push({ text: cleanInline(text.slice(lastIndex)), strong: false });
  }

  return parts.filter((part) => part.text.length > 0);
}

function renderInlineText(text: string) {
  const parts = parseInlineStrong(text);
  if (parts.length === 0) return normalizeInlineText(text);

  return parts.map((part, index) =>
    part.strong ? (
      <strong key={`${part.text}-${index}`} className="font-semibold text-on-surface">
        {part.text}
      </strong>
    ) : (
      <Fragment key={`${part.text}-${index}`}>{part.text}</Fragment>
    )
  );
}

function parseHeading(line: string) {
  const match = line.match(/^(#{1,6})\s+(.+)$/);
  if (!match) return null;
  return {
    level: match[1].length,
    text: normalizeInlineText(match[2]),
  };
}

function parseListItem(line: string) {
  const numbered = line.match(/^(\d+)\.\s+(.+)$/);
  if (numbered) {
    return {
      kind: "numbered" as const,
      marker: `${numbered[1]}.`,
      text: normalizeInlineText(numbered[2]),
    };
  }

  const bulleted = line.match(/^[-*]\s+(.+)$/);
  if (bulleted) {
    return {
      kind: "bulleted" as const,
      marker: "•",
      text: normalizeInlineText(bulleted[1]),
    };
  }

  return null;
}

function isMarkdownDivider(line: string) {
  return /^\s*([-*_]\s*){3,}$/.test(line.trim());
}

function normalizeTableCells(line: string) {
  const cells = line.split("|").map((cell) => cell.trim());
  if (cells[0] === "") cells.shift();
  if (cells.at(-1) === "") cells.pop();
  return cells;
}

function isMarkdownTableDivider(line: string) {
  const segments = normalizeTableCells(line);
  return segments.length > 1 && segments.every((segment) => /^:?-{3,}:?$/.test(segment));
}

function isTableRow(line: string) {
  const pipeCount = (line.match(/\|/g) ?? []).length;
  return pipeCount >= 2;
}

function isComputationLine(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  const hasDigits = /\d/.test(trimmed);
  const hasMathPattern = /=|\d\s*[-%*+/]\s*\d|\b(total|sum|avg|average|difference|profit|loss)\b/i.test(trimmed);
  return hasDigits && hasMathPattern;
}

function parseTableBlock(lines: string[], startIndex: number) {
  const currentLine = lines[startIndex];
  const nextLine = lines[startIndex + 1] ?? "";

  if (!isTableRow(currentLine) || !isMarkdownTableDivider(nextLine)) {
    return null;
  }

  const headers = normalizeTableCells(currentLine);
  const rows: string[][] = [];
  let index = startIndex + 2;

  while (index < lines.length && lines[index].trim() && isTableRow(lines[index])) {
    rows.push(normalizeTableCells(lines[index]));
    index += 1;
  }

  if (headers.length === 0 || rows.length === 0) {
    return null;
  }

  return {
    block: { type: "table" as const, headers, rows },
    nextIndex: index,
  };
}

function collectParagraphLines(lines: string[], startIndex: number) {
  const paragraphLines: string[] = [];
  let index = startIndex;

  while (index < lines.length && lines[index].trim()) {
    paragraphLines.push(lines[index]);
    index += 1;
  }

  return { paragraphLines, nextIndex: index };
}

function parseMentorBlocks(content: string): MentorBlock[] {
  const lines = content.split("\n");
  const blocks: MentorBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    const tableResult = parseTableBlock(lines, i);
    if (tableResult) {
      blocks.push(tableResult.block);
      i = tableResult.nextIndex;
      continue;
    }

    const paragraphResult = collectParagraphLines(lines, i);
    blocks.push({ type: "paragraph", lines: paragraphResult.paragraphLines });
    i = paragraphResult.nextIndex;
  }

  return blocks;
}

export function MentorMessageContent({ content }: Readonly<{ content: string }>) {
  const cleanContent = stripThinkTags(content);
  const blocks = parseMentorBlocks(cleanContent);

  return (
    <div className="space-y-4">
      {blocks.map((block, blockIndex) => {
        const blockKey = `${block.type}-${blockIndex}-${
          block.type === "table" ? block.headers.join("|") : block.lines.join("|")
        }`;

        if (block.type === "table") {
          return (
            <div
              key={blockKey}
              className="overflow-x-auto rounded-2xl border border-outline-subtle bg-paper p-xs"
            >
              <table className="min-w-full border-separate border-spacing-0 text-left">
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th
                        key={`${header}-${headerIndex}`}
                        className="border-b border-outline-subtle bg-surface-low px-sm py-xs font-label-sm text-[11px] font-semibold tracking-wide text-on-surface-variant"
                      >
                        {renderInlineText(header)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`row-${blockIndex}-${rowIndex}`}>
                      {block.headers.map((_, colIndex) => (
                        <td
                          key={`cell-${blockIndex}-${rowIndex}-${colIndex}`}
                          className="border-b border-outline-subtle/70 px-sm py-xs font-body-md text-body-md text-on-surface"
                        >
                          {renderCellContent(row[colIndex] ?? "-")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return (
          <div key={blockKey} className="space-y-xs">
            {block.lines.map((line, lineIndex) => {
              const heading = parseHeading(line);
              if (heading) {
                return (
                  <p
                    key={`heading-${blockIndex}-${lineIndex}`}
                    className={`font-title-md text-on-surface ${heading.level <= 2 ? "text-[19px] font-semibold" : "text-[16px] font-semibold"}`}
                  >
                    {renderInlineText(heading.text)}
                  </p>
                );
              }

              if (isMarkdownDivider(line)) {
                return <div key={`divider-${blockIndex}-${lineIndex}`} className="my-xs border-b border-outline-subtle" />;
              }

              const listItem = parseListItem(line);
              if (listItem) {
                return (
                  <div key={`list-${blockIndex}-${lineIndex}`} className="flex items-start gap-3 rounded-xl bg-surface-low px-3 py-2">
                    <span className="mt-[1px] min-w-[22px] font-label-sm text-[12px] font-bold text-primary">{listItem.marker}</span>
                    <p className="font-message text-[16px] leading-relaxed text-on-surface">{renderInlineText(listItem.text)}</p>
                  </div>
                );
              }

              if (isComputationLine(line)) {
                return (
                  <div
                    key={`calc-${blockIndex}-${lineIndex}`}
                    className="rounded-xl border border-secondary/20 bg-indigo-mist px-3 py-2 font-mono text-[13px] text-secondary"
                  >
                    {renderInlineText(line)}
                  </div>
                );
              }

              return (
                <p key={`line-${blockIndex}-${lineIndex}`} className="font-message text-message leading-relaxed text-on-surface whitespace-pre-line">
                  {renderInlineText(line)}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

