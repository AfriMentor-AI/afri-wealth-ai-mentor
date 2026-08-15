"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchChatMessages, sendMessage, tagCommitment } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MentorMessageContent({ content }: Readonly<{ content: string }>) {
  return (
    <ReactMarkdown
      className="space-y-sm"
      components={{
        p: ({ children }) => <p className="font-body-md whitespace-pre-line">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-on-surface">{children}</strong>,
        h1: ({ children }) => <p className="font-title-md text-on-surface text-[16px] font-semibold">{children}</p>,
        h2: ({ children }) => <p className="font-title-md text-on-surface text-[16px] font-semibold">{children}</p>,
        h3: ({ children }) => <p className="font-title-md text-on-surface text-[14px] font-semibold">{children}</p>,
        h4: ({ children }) => <p className="font-title-md text-on-surface text-[14px] font-semibold">{children}</p>,
        h5: ({ children }) => <p className="font-title-md text-on-surface text-[14px] font-semibold">{children}</p>,
        h6: ({ children }) => <p className="font-title-md text-on-surface text-[14px] font-semibold">{children}</p>,
        hr: () => <div className="my-xs border-b border-outline-variant/70" />,
        ul: ({ children }) => <div className="space-y-xs">{children}</div>,
        ol: ({ children }) => <div className="space-y-xs">{children}</div>,
        li: ({ children, ordered }) => (
          <div className="flex items-start gap-xs rounded-md bg-surface-container px-sm py-xs">
            <span className="mt-[1px] min-w-[22px] font-label-sm text-[12px] text-secondary">
              {ordered ? `${children[0].key}.` : "•"}
            </span>
            <p className="font-body-md text-body-md text-on-surface">{children}</p>
          </div>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto rounded-lg border border-outline-variant bg-surface-container-high p-xs">
            <table className="min-w-full border-separate border-spacing-0 text-left">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-b border-outline-variant bg-surface-container px-sm py-xs font-label-sm text-[11px] uppercase tracking-wide text-on-surface-variant">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border-b border-outline-variant/70 px-sm py-xs font-body-md text-body-md text-on-surface">
            {children}
          </td>
        ),
        code: ({ children }) => (
          <div className="rounded-md border border-secondary/40 bg-secondary-container px-sm py-xs font-code text-[12px] text-on-secondary-container">
            {children}
          </div>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export default function ChatPage() {
  const { chatMessages, chatDraft, profile, chatSessionId, activeGoalId } = useAppState();
  const dispatch = useAppDispatch();
  const [isRecording, setIsRecording] = useState(false);
  const [commitmentTagged, setCommitmentTagged] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  async function send() {
    if (!chatDraft.trim() || !chatSessionId) return;

    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      userId: profile?.userId ?? "local-user",
      sender: "user",
      content: chatDraft.trim(),
      created_at: new Date().toISOString(),
    };
    dispatch({ type: "APPEND_CHAT_MESSAGE", message: userMessage });
    dispatch({ type: "SET_CHAT_DRAFT", draft: "" });

    try {
      const assistantMessage = await sendMessage(chatSessionId, userMessage.content);
      dispatch({ type: "APPEND_CHAT_MESSAGE", message: assistantMessage });
    } catch (error) {
      console.error("Failed to send message:", error);
      // Optional: show error message in UI, maybe as a special chat message
    }
  }

  async function handleTagCommitment() {
    if (!chatSessionId || !activeGoalId || chatMessages.length === 0) {
      // Maybe show a notification to the user that they need to select a goal first.
      console.error("Cannot tag commitment without a session, active goal, and a message.");
      return;
    }
    const lastMessage = chatMessages[chatMessages.length - 1];
    if (lastMessage.sender !== "mentor" || !lastMessage.is_commitment_candidate) {
      return;
    }

    try {
      await tagCommitment(chatSessionId, lastMessage.id, activeGoalId);
      setCommitmentTagged(true);
    } catch (error) {
      console.error("Failed to tag commitment:", error);
      // Optional: show an error message to the user
    }
  }

  const lastIsMentor = chatMessages.length > 0 && chatMessages[chatMessages.length - 1].sender === "mentor";

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-outline-variant px-margin-mobile py-md">
        <div className="flex items-center gap-sm">
          <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-full border-2 border-primary">
            <Image src="/images/chioma-avatar.png" alt="Chioma" fill className="object-cover" />
            <span
              aria-hidden
              className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-surface bg-secondary"
            />
          </div>
          <div>
            <p className="font-title-md text-title-md text-primary">CHIOMA</p>
            <p className="flex items-center gap-xs font-label-sm text-label-sm text-on-surface-variant">
              <span className="h-1.5 w-1.5 rounded-full bg-secondary" /> online
            </p>
          </div>
        </div>
        <ThemeToggle />
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-margin-mobile py-lg">
        <div className="flex flex-col gap-lg">
          {chatMessages.map((m) => (
            <div key={m.id} className={`flex max-w-[85%] flex-col ${m.sender === "user" ? "items-end self-end" : "items-start"}`}>
              <div
                className={`p-md text-body-md ${
                  m.sender === "user"
                    ? "rounded rounded-tr-none bg-primary-container text-on-primary-container shadow-sm"
                    : "rounded rounded-tl-none border border-outline-variant bg-surface-container-low text-on-surface shadow-sm"
                }`}
              >
                {m.sender === "mentor" ? (
                  <MentorMessageContent content={m.content} />
                ) : (
                  <p className="font-body-md whitespace-pre-line">{m.content}</p>
                )}
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-sm inline-flex items-center gap-xs rounded-full border border-outline-variant bg-surface-container-highest px-sm py-xs">
                    <Icon name="auto_stories" size={16} />
                    <span className="font-label-sm text-[11px] text-on-surface-variant">{m.citations[0].label}</span>
                  </div>
                )}
              </div>
              <span className="mt-xs font-label-sm text-[10px] text-on-surface-variant">{formatTime(m.created_at)}</span>
            </div>
          ))}

          {lastIsMentor && chatMessages[chatMessages.length - 1].is_commitment_candidate && !commitmentTagged && (
            <div className="flex items-center justify-between gap-md rounded border border-secondary bg-secondary-container p-md">
              <div className="flex items-center gap-sm">
                <Icon name="workspace_premium" filled className="text-secondary" />
                <span className="font-body-md text-body-md font-semibold text-on-secondary-container">
                  Tag 10% daily reserve as a commitment?
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
      </div>

      <div className="flex shrink-0 items-center gap-sm border-t border-outline-variant px-margin-mobile py-sm">
        <button
          type="button"
          aria-label="Attach a file"
          className="tap-target flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low"
        >
          <Icon name="attach_file" />
        </button>
        <button
          type="button"
          aria-label={isRecording ? "Stop recording voice note" : "Record a voice note"}
          onClick={() => setIsRecording((r) => !r)}
          className={`tap-target flex items-center justify-center rounded-full ${
            isRecording ? "animate-pulse bg-error text-on-error" : "text-on-surface-variant hover:bg-surface-container-low"
          }`}
        >
          <Icon name="mic" />
        </button>
        <input
          value={chatDraft}
          onChange={(e) => dispatch({ type: "SET_CHAT_DRAFT", draft: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={isRecording ? "Recording... tap mic again to stop" : "Ask Chioma anything"}
          className="flex-1 rounded-full border border-outline-variant bg-surface-container-lowest px-md py-sm font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
        />
        <button
          type="button"
          aria-label="Send message"
          onClick={send}
          disabled={!chatDraft.trim()}
          className="tap-target flex items-center justify-center rounded-full bg-primary text-on-primary disabled:opacity-40"
        >
          <Icon name="send" />
        </button>
      </div>
    </div>
  );
}
