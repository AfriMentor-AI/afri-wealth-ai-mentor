"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ConversationList } from "@/components/ConversationList";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchChatMessages, sendMessageStream, stripThinkTags, tagCommitment, createGoal, fetchGoals } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { startAudioRecording, playTextToSpeech, stopCurrentSpeech, type ActiveRecording } from "@/lib/voice";
import { CitationViewerModal } from "@/components/CitationViewerModal";

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

type MentorBlock =
  | { type: "paragraph"; lines: string[] }
  | { type: "table"; headers: string[]; rows: string[][] };

function normalizeInlineText(value: string) {
  return value
    .replaceAll("`", "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .trim();
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
      parts.push({ text: normalizeInlineText(text.slice(lastIndex, match.index)), strong: false });
    }
    parts.push({ text: normalizeInlineText(match[1]), strong: true });
    lastIndex = match.index + match[0].length;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    parts.push({ text: normalizeInlineText(text.slice(lastIndex)), strong: false });
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

function MentorMessageContent({ content }: Readonly<{ content: string }>) {
  const cleanContent = stripThinkTags(content);
  const blocks = parseMentorBlocks(cleanContent);

  return (
    <div className="space-y-sm">
      {blocks.map((block, blockIndex) => {
        const blockKey = `${block.type}-${blockIndex}-${
          block.type === "table" ? block.headers.join("|") : block.lines.join("|")
        }`;

        if (block.type === "table") {
          return (
            <div
              key={blockKey}
              className="overflow-x-auto rounded-lg border border-outline-variant bg-surface-container-high p-xs"
            >
              <table className="min-w-full border-separate border-spacing-0 text-left">
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th
                        key={`${header}-${headerIndex}`}
                        className="border-b border-outline-variant bg-surface-container px-sm py-xs font-label-sm text-[11px] uppercase tracking-wide text-on-surface-variant"
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
                          className="border-b border-outline-variant/70 px-sm py-xs font-body-md text-body-md text-on-surface"
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
                    className={`font-title-md text-on-surface ${heading.level <= 2 ? "text-[16px] font-semibold" : "text-[14px] font-semibold"}`}
                  >
                    {renderInlineText(heading.text)}
                  </p>
                );
              }

              if (isMarkdownDivider(line)) {
                return <div key={`divider-${blockIndex}-${lineIndex}`} className="my-xs border-b border-outline-variant/70" />;
              }

              const listItem = parseListItem(line);
              if (listItem) {
                return (
                  <div key={`list-${blockIndex}-${lineIndex}`} className="flex items-start gap-xs rounded-md bg-surface-container px-sm py-xs">
                    <span className="mt-[1px] min-w-[22px] font-label-sm text-[12px] text-secondary">{listItem.marker}</span>
                    <p className="font-body-md text-body-md text-on-surface">{renderInlineText(listItem.text)}</p>
                  </div>
                );
              }

              if (isComputationLine(line)) {
                return (
                  <div
                    key={`calc-${blockIndex}-${lineIndex}`}
                    className="rounded-md border border-secondary/40 bg-secondary-container px-sm py-xs font-code text-[12px] text-on-secondary-container"
                  >
                    {renderInlineText(line)}
                  </div>
                );
              }

              return (
                <p key={`line-${blockIndex}-${lineIndex}`} className="font-body-md whitespace-pre-line">
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

/** Three animated dots shown while waiting for the first streaming token. */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-[5px] px-md py-sm">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-on-surface-variant animate-bounce"
          style={{ animationDelay: `${i * 0.18}s`, animationDuration: "0.9s" }}
        />
      ))}
    </div>
  );
}

export default function ChatPage() {
  const { chatMessages, chatDraft, profile, chatSessionId, activeGoalId, selectedPersona } = useAppState();
  const dispatch = useAppDispatch();
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [playingAudioMessageId, setPlayingAudioMessageId] = useState<string | null>(null);
  const activeRecordingRef = useRef<ActiveRecording | null>(null);
  const [commitmentTagged, setCommitmentTagged] = useState(false);
  const [goalPickerGoals, setGoalPickerGoals] = useState<{ id: string; title: string }[] | null>(null);
  const [newGoalInput, setNewGoalInput] = useState("");
  const [showConversations, setShowConversations] = useState(false);
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<{
    label: string;
    messageContext: string;
  } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortStreamRef = useRef<(() => void) | null>(null);

  function cleanTextForSpeech(text: string): string {
    return stripThinkTags(text)
      .replace(/[#*_`~]/g, "")
      .replace(/\|[-:\s|]+\|/g, "")
      .replace(/\|/g, ", ")
      .replace(/\n+/g, ". ")
      .trim();
  }

  async function toggleVoiceRecording() {
    if (isRecording) {
      setIsRecording(false);
      setIsTranscribing(true);
      try {
        if (activeRecordingRef.current) {
          const text = await activeRecordingRef.current.stop();
          activeRecordingRef.current = null;
          if (text && text.trim()) {
            // Send the voice message immediately and automatically speak the mentor's reply!
            send(text.trim(), true);
          }
        }
      } catch (err) {
        console.error("Voice transcription error:", err);
      } finally {
        setIsTranscribing(false);
      }
    } else {
      try {
        const recording = await startAudioRecording((interim) => {
          if (interim) {
            dispatch({ type: "SET_CHAT_DRAFT", draft: interim });
          }
        });
        activeRecordingRef.current = recording;
        setIsRecording(true);
      } catch (err) {
        console.error("Microphone access error:", err);
        alert("Please enable microphone permissions in your browser to record voice notes.");
      }
    }
  }

  async function handlePlayTTS(messageId: string, text: string) {
    if (playingAudioMessageId === messageId) {
      stopCurrentSpeech();
      setPlayingAudioMessageId(null);
      return;
    }
    const clean = cleanTextForSpeech(text);
    if (!clean) return;

    try {
      setPlayingAudioMessageId(messageId);
      await playTextToSpeech(clean, selectedPersona?.id || "chioma", () => {
        setPlayingAudioMessageId(null);
      });
    } catch (err) {
      console.error("TTS playback error:", err);
      setPlayingAudioMessageId(null);
    }
  }

  useEffect(() => {
    if (chatSessionId && chatMessages.length === 0) {
      fetchChatMessages(chatSessionId).then((messages) => {
        dispatch({ type: "SET_CHAT_MESSAGES", messages });
      });
    }
  }, [chatSessionId, chatMessages.length, dispatch]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatMessages.length]);

  useEffect(() => {
    if (streamingContent !== null) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [streamingContent]);

  function send(customText?: string | React.MouseEvent, autoPlayVoiceReply = false) {
    const textToSend = (typeof customText === "string" ? customText : chatDraft).trim();

    if (!textToSend || !chatSessionId || isTyping) return;

    // Abort any in-flight stream before starting a new one
    abortStreamRef.current?.();

    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      userId: profile?.userId ?? "local-user",
      sender: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };
    dispatch({ type: "APPEND_CHAT_MESSAGE", message: userMessage });
    dispatch({ type: "SET_CHAT_DRAFT", draft: "" });

    setIsTyping(true);
    setStreamingContent(null);

    const abort = sendMessageStream(
      chatSessionId,
      userMessage.content,
      (chunk) => {
        // First token — replace dots with the streaming bubble
        setIsTyping(false);
        setStreamingContent((prev) => (prev ?? "") + chunk);
      },
      (assistantMessage) => {
        // Stream complete — swap streaming bubble for the final persisted message
        setStreamingContent(null);
        setIsTyping(false);
        dispatch({ type: "APPEND_CHAT_MESSAGE", message: assistantMessage });
        setCommitmentTagged(false);
        abortStreamRef.current = null;

        // Auto-play mentor's audio reply if message was sent via voice!
        if (autoPlayVoiceReply && assistantMessage.content) {
          handlePlayTTS(assistantMessage.id, assistantMessage.content);
        }
      },
      (error) => {
        console.error("Stream error:", error);
        setStreamingContent(null);
        setIsTyping(false);
        abortStreamRef.current = null;
      },
    );

    abortStreamRef.current = abort;
  }

  async function handleTagCommitment() {
    if (!chatSessionId || chatMessages.length === 0) return;
    const lastMessage = chatMessages[chatMessages.length - 1];
    if (lastMessage.sender !== "mentor" || !lastMessage.is_commitment_candidate) return;

    if (activeGoalId) {
      await confirmTagWithGoal(activeGoalId);
      return;
    }

    try {
      const goals = await fetchGoals();
      if (goals.length === 1) {
        dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: goals[0].id });
        await confirmTagWithGoal(goals[0].id);
      } else if (goals.length > 1) {
        setGoalPickerGoals(goals.map((g) => ({ id: g.id, title: g.title })));
      } else {
        const newGoal = await createGoal({ title: "My Financial Goal", description: null });
        dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: newGoal.id });
        await confirmTagWithGoal(newGoal.id);
      }
    } catch (e) {
      console.warn("Could not retrieve goals:", e);
    }
  }

  async function confirmTagWithGoal(goalId: string) {
    if (!chatSessionId || chatMessages.length === 0) return;
    const lastMessage = chatMessages[chatMessages.length - 1];
    setGoalPickerGoals(null);
    setNewGoalInput("");
    try {
      await tagCommitment(chatSessionId, lastMessage.id, goalId);
      dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId });
      setCommitmentTagged(true);
    } catch (error) {
      console.error("Failed to tag commitment:", error);
    }
  }

  const lastIsMentor = chatMessages.length > 0 && chatMessages[chatMessages.length - 1].sender === "mentor";

  const mentorName = selectedPersona?.name ?? "CHIOMA";

  return (
    <div className="flex h-full md:flex-row">
      {/* Desktop: collapsible conversation list pane */}
      <aside className={`hidden shrink-0 border-r border-outline-variant md:block transition-all duration-200 ${desktopSidebarOpen ? "w-72" : "w-0 overflow-hidden border-r-0"}`}>
        <ConversationList />
      </aside>

      {/* Mobile: full-screen slide-over for the same list. */}
      {showConversations && (
        <div className="fixed inset-0 z-30 bg-surface md:hidden">
          <div className="flex h-full flex-col">
            <div className="flex h-16 shrink-0 items-center gap-sm border-b border-outline-variant px-margin-mobile">
              <button
                type="button"
                aria-label="Close conversation list"
                onClick={() => setShowConversations(false)}
                className="tap-target flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low"
              >
                <Icon name="arrow_back" />
              </button>
              <p className="font-title-md text-title-md text-on-surface">Conversations</p>
            </div>
            <div className="flex-1 overflow-hidden">
              <ConversationList onSelect={() => setShowConversations(false)} />
            </div>
          </div>
        </div>
      )}

      <div className="flex h-full flex-1 flex-col bg-surface-bright md:bg-surface">
        <div className="flex shrink-0 items-center justify-between border-b border-outline-variant px-margin-mobile py-md md:px-lg">
          <div className="flex items-center gap-sm md:gap-md">
            {/* Mobile: open slide-over */}
            <button
              type="button"
              aria-label="Show conversations"
              onClick={() => setShowConversations(true)}
              className="tap-target flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low md:hidden"
            >
              <Icon name="forum" />
            </button>
            {/* Desktop: toggle sidebar */}
            <button
              type="button"
              aria-label={desktopSidebarOpen ? "Hide sidebar" : "Show sidebar"}
              onClick={() => setDesktopSidebarOpen((v) => !v)}
              className="tap-target hidden items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low md:flex"
            >
              <Icon name={desktopSidebarOpen ? "menu_open" : "menu"} />
            </button>
            <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-full border-2 border-primary">
              <Image src="/images/chioma-avatar.png" alt={mentorName} fill className="object-cover" />
              <span
                aria-hidden
                className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-surface bg-secondary"
              />
            </div>
            <div>
              <div className="flex items-center gap-sm">
                <p className="font-title-md text-title-md text-primary">{mentorName.toUpperCase()}</p>
                <span className="hidden rounded bg-secondary-container px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-tighter text-on-secondary-container md:inline">
                  Mentor
                </span>
              </div>
              <p className="flex items-center gap-xs font-label-sm text-label-sm text-on-surface-variant">
                <span className="h-1.5 w-1.5 rounded-full bg-secondary" /> online
              </p>
            </div>
          </div>
          <div className="flex items-center gap-sm">
            {playingAudioMessageId && (
              <button
                type="button"
                onClick={() => {
                  stopCurrentSpeech();
                  setPlayingAudioMessageId(null);
                }}
                className="flex items-center gap-1.5 rounded-full bg-primary/15 border border-primary/30 px-3 py-1 text-[11px] font-semibold text-primary animate-pulse hover:bg-primary/25 transition-colors"
                aria-label="Stop audio reply"
              >
                <Icon name="volume_up" size={14} />
                <span>Speaking... (tap to mute)</span>
              </button>
            )}
            <ThemeToggle />
          </div>
        </div>

      <div ref={scrollRef} role="log" aria-label={`Chat with ${mentorName}`} className="flex-1 overflow-y-auto px-margin-mobile py-lg md:px-0">
        <div className="mx-auto flex max-w-3xl flex-col gap-lg md:px-lg">
          {chatMessages.map((m) => (
            <div key={m.id} className={`flex max-w-[85%] flex-col ${m.sender === "user" ? "items-end self-end" : "items-start"}`}>
              <div
                className={`p-md text-body-md md:rounded-xl md:shadow-sm ${
                  m.sender === "user"
                    ? "rounded rounded-tr-none bg-primary-container text-on-primary-container shadow-sm md:rounded-tr-xl"
                    : "rounded rounded-tl-none border border-outline-variant bg-surface-container-low text-on-surface shadow-sm md:rounded-tl-xl"
                }`}
              >
                {m.sender === "mentor" ? (
                  <MentorMessageContent content={m.content} />
                ) : (
                  <p className="font-body-md whitespace-pre-line">{m.content}</p>
                )}
                {m.citations && m.citations.length > 0 && (
                   <button
                    type="button"
                    onClick={() =>
                      setActiveCitation({
                        label: m.citations![0].label,
                        messageContext: m.content,
                      })
                    }
                    className="mt-sm inline-flex items-center gap-xs rounded-full border border-outline-variant bg-surface-container-highest px-sm py-xs text-left transition-all hover:border-primary/50 hover:bg-primary-container/30 active:scale-95 cursor-pointer shadow-xs"
                    title="Click to view verified RAG knowledge source"
                  >
                    <Icon name="auto_stories" size={16} className="text-primary" />
                    <span className="font-label-sm text-[11px] font-semibold text-on-surface">
                      Based on {m.citations[0].label}
                    </span>
                    <Icon name="info" size={14} className="text-primary/70" />
                  </button>
                )}
              </div>
              <div className="mt-xs flex items-center gap-sm">
                <span className="font-label-sm text-[10px] text-on-surface-variant">{formatTime(m.created_at)}</span>
                {m.sender === "mentor" && (
                  <button
                    type="button"
                    aria-label={playingAudioMessageId === m.id ? "Stop voice playback" : "Listen to mentor reply"}
                    onClick={() => handlePlayTTS(m.id, m.content)}
                    className="inline-flex items-center gap-1 rounded-full border border-outline-variant/60 bg-surface-container-high px-2 py-0.5 text-[11px] font-medium text-on-surface-variant hover:bg-surface-container-highest hover:text-primary transition-colors"
                  >
                    <Icon name={playingAudioMessageId === m.id ? "stop" : "volume_up"} size={14} />
                    <span>{playingAudioMessageId === m.id ? "Stop" : "Listen"}</span>
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Typing indicator — three dots while waiting for first token or while model is thinking */}
          {(isTyping || (streamingContent !== null && !stripThinkTags(streamingContent))) && (
            <div className="flex max-w-[85%] flex-col items-start">
              <div className="rounded rounded-tl-none border border-outline-variant bg-surface-container-low shadow-sm md:rounded-tl-xl">
                <TypingIndicator />
              </div>
            </div>
          )}

          {/* Streaming bubble — grows token-by-token once real content is available */}
          {streamingContent !== null && Boolean(stripThinkTags(streamingContent)) && (
            <div className="flex max-w-[85%] flex-col items-start">
              <div className="rounded rounded-tl-none border border-outline-variant bg-surface-container-low p-md text-body-md text-on-surface shadow-sm md:rounded-tl-xl">
                <MentorMessageContent content={streamingContent} />
                <span className="inline-block h-3 w-0.5 animate-pulse bg-primary align-middle ml-0.5" aria-hidden />
              </div>
            </div>
          )}

          {lastIsMentor && chatMessages[chatMessages.length - 1].is_commitment_candidate && !commitmentTagged && (
            <div className="rounded border border-secondary bg-secondary-container p-md md:rounded-xl">
              {goalPickerGoals ? (
                <div className="flex flex-col gap-sm">
                  <span className="font-body-md text-body-md font-semibold text-on-secondary-container">Which goal should this go under?</span>
                  {goalPickerGoals.map((g) => (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => confirmTagWithGoal(g.id)}
                      className="tap-target rounded-full bg-secondary px-md py-sm text-left font-label-sm text-label-sm text-on-secondary transition-transform active:scale-95"
                    >
                      {g.title}
                    </button>
                  ))}
                  {newGoalInput === "" ? (
                    <button
                      type="button"
                      onClick={() => setNewGoalInput(" ")}
                      className="tap-target flex items-center gap-sm rounded-full border border-dashed border-secondary px-md py-sm text-left font-label-sm text-label-sm text-secondary transition-colors hover:bg-secondary/10"
                    >
                      <Icon name="add" size={16} />
                      New goal
                    </button>
                  ) : (
                    <form
                      className="flex items-center gap-sm"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const title = newGoalInput.trim();
                        if (!title) return;
                        const created = await createGoal({ title });
                        await confirmTagWithGoal(created.id);
                      }}
                    >
                      <input
                        autoFocus
                        value={newGoalInput.trimStart()}
                        onChange={(e) => setNewGoalInput(e.target.value)}
                        placeholder="Goal name…"
                        className="min-w-0 flex-1 rounded-full border border-secondary bg-transparent px-md py-sm font-label-sm text-label-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-1 focus:ring-secondary"
                      />
                      <button
                        type="submit"
                        disabled={!newGoalInput.trim()}
                        className="tap-target rounded-full bg-secondary px-md py-sm font-label-sm text-label-sm text-on-secondary disabled:opacity-40"
                      >
                        Create
                      </button>
                    </form>
                  )}
                  <button type="button" onClick={() => setGoalPickerGoals(null)} className="font-label-sm text-label-sm text-outline">
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-md">
                  <div className="flex items-center gap-sm">
                    <Icon name="workspace_premium" filled className="text-secondary" />
                    <span className="font-body-md text-body-md font-semibold text-on-secondary-container">
                      Tag this as a commitment?
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleTagCommitment}
                    className="tap-target rounded-full bg-secondary px-md py-sm font-label-sm text-label-sm text-on-secondary transition-transform active:scale-95"
                  >
                    Yes, Tag It
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-3xl shrink-0 items-center gap-sm border-t border-outline-variant px-margin-mobile py-sm md:px-lg md:py-md">
        <button
          type="button"
          aria-label="Attach a file"
          className="tap-target flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low"
        >
          <Icon name="attach_file" />
        </button>
        <button
          type="button"
          aria-label={
            isTranscribing
              ? "Transcribing voice note..."
              : isRecording
              ? "Stop recording voice note"
              : "Record a voice note"
          }
          onClick={toggleVoiceRecording}
          disabled={isTranscribing}
          className={`tap-target flex items-center justify-center rounded-full transition-all ${
            isRecording
              ? "animate-pulse bg-error text-on-error shadow-md ring-2 ring-error/40"
              : isTranscribing
              ? "bg-surface-container-high text-primary"
              : "text-on-surface-variant hover:bg-surface-container-low"
          }`}
        >
          <Icon name={isTranscribing ? "hourglass_empty" : isRecording ? "graphic_eq" : "mic"} />
        </button>
        <input
          value={chatDraft}
          onChange={(e) => dispatch({ type: "SET_CHAT_DRAFT", draft: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && send()}
          aria-label={`Message ${mentorName}`}
          placeholder={
            isRecording
              ? "Recording voice note... tap the red button to finish"
              : isTranscribing
              ? "Transcribing your voice note..."
              : `Ask ${mentorName} anything`
          }
          className="flex-1 rounded-full border border-outline-variant bg-surface-container-lowest px-md py-sm font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary md:py-md"
        />
        <button
          type="button"
          aria-label="Send message"
          onClick={() => send()}
          disabled={!chatDraft.trim() || isTyping || streamingContent !== null || isRecording || isTranscribing}
          className="tap-target flex items-center justify-center rounded-full bg-primary text-on-primary disabled:opacity-40"
        >
          <Icon name="send" />
        </button>
      </div>
      </div>
       {/* Citation / RAG Knowledge Viewer Modal */}
      <CitationViewerModal
        citationLabel={activeCitation?.label ?? null}
        messageContext={activeCitation?.messageContext}
        onClose={() => setActiveCitation(null)}
        onAskFollowUp={(prompt) => {
          setActiveCitation(null);
          dispatch({ type: "SET_CHAT_DRAFT", draft: prompt });
        }}
      />
    </div>
  );
}