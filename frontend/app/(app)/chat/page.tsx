"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchChatMessages, sendMessage, tagCommitment } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
      createdAt: new Date().toISOString(),
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
    if (lastMessage.sender !== "mentor" || !lastMessage.isCommitmentCandidate) {
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
                <p className="font-body-md whitespace-pre-line">{m.content}</p>
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-sm inline-flex items-center gap-xs rounded-full border border-outline-variant bg-surface-container-highest px-sm py-xs">
                    <Icon name="auto_stories" size={16} />
                    <span className="font-label-sm text-[11px] text-on-surface-variant">{m.citations[0].label}</span>
                  </div>
                )}
              </div>
              <span className="mt-xs font-label-sm text-[10px] text-on-surface-variant">{formatTime(m.createdAt)}</span>
            </div>
          ))}

          {lastIsMentor && chatMessages[chatMessages.length - 1].isCommitmentCandidate && !commitmentTagged && (
            <div className="flex items-center justify-between gap-md rounded border border-secondary bg-secondary-container p-md">
              <div className="flex items-center gap-sm">
                <Icon name="workspace_premium" filled className="text-secondary" />
                <span className="font-body-md text-body-md font-semibold text-on-secondary-container">
                  Tag 10% daily reserve as a commitment?
                </span>
              </div>
              <button
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
        <button aria-label="Attach a file" className="tap-target flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low">
          <Icon name="attach_file" />
        </button>
        <button
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
