"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "./Icon";
import { fetchChatMessages, fetchChatSessions, fetchPersonas } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { useAppDispatch, useAppState } from "@/lib/store";

function initials(name: string) {
  return name
    .replace("The ", "")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Multi-mentor conversation list — GET /api/v1/chat/sessions joined against
 * the persona catalogue for display names. Shared between the desktop
 * sidebar pane and the mobile slide-over (see ChatPage). */
export function ConversationList({ onSelect }: { onSelect?: () => void }) {
  const { chatSessions, chatSessionId } = useAppState();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);

  useEffect(() => {
    fetchPersonas().then(setPersonas);
    fetchChatSessions()
      .then((sessions) => dispatch({ type: "SET_CHAT_SESSIONS", sessions }))
      .catch((err) => console.error("Failed to load conversations:", err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function personaFor(id: string | null): Persona | null {
    return personas?.find((p) => p.id === id) ?? null;
  }

  async function openConversation(sessionId: string) {
    if (sessionId !== chatSessionId) {
      dispatch({ type: "SET_CHAT_SESSION_ID", sessionId });
      const session = chatSessions.find((s) => s.id === sessionId);
      const persona = personaFor(session?.personaId ?? null);
      if (persona) dispatch({ type: "SET_PERSONA", persona });
      const messages = await fetchChatMessages(sessionId);
      dispatch({ type: "SET_CHAT_MESSAGES", messages });
    }
    onSelect?.();
  }

  return (
    <div className="flex h-full flex-col bg-surface">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-outline-variant px-md">
        <h2 className="font-title-md text-title-md text-on-surface">Conversations</h2>
        <Link
          href="/persona"
          aria-label="Start a new conversation"
          className="tap-target flex items-center justify-center rounded-full p-sm text-on-surface-variant hover:bg-surface-variant"
        >
          <Icon name="edit_note" />
        </Link>
      </header>
      <div className="flex-1 overflow-y-auto">
        {chatSessions.length === 0 && (
          <p className="p-md font-body-md text-body-md text-on-surface-variant">
            No conversations yet — choose a mentor to start one.
          </p>
        )}
        {chatSessions.map((s) => {
          const persona = personaFor(s.personaId);
          const isActive = s.id === chatSessionId;
          return (
            <button
              key={s.id}
              onClick={() => openConversation(s.id)}
              className={`flex w-full items-center gap-md border-b border-outline-variant/30 p-md text-left transition-colors ${
                isActive ? "border-l-4 border-l-primary bg-surface-container" : "hover:bg-surface-variant/30"
              }`}
            >
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary-fixed-dim font-headline-lg-mobile text-[16px] text-on-primary-container">
                {persona ? initials(persona.name) : "?"}
              </div>
              <div className="flex flex-1 flex-col overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="truncate font-title-md text-sm text-on-surface">
                    {persona?.name ?? "Unknown mentor"}
                  </span>
                  <span className="shrink-0 text-[10px] text-on-surface-variant">{timeAgo(s.lastMessageAt)}</span>
                </div>
                <p className="truncate text-sm text-on-surface-variant">
                  {s.lastMessagePreview ?? "No messages yet"}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
