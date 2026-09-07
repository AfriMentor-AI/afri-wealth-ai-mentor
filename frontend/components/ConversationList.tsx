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

export function ConversationList({ onSelect }: { onSelect?: () => void }) {
  const { chatSessions, chatSessionId } = useAppState();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);
  const [expandedPersonas, setExpandedPersonas] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchPersonas().then((ps) => {
      setPersonas(ps);
      // Auto-expand the persona that owns the active session
      if (ps && chatSessionId) {
        const activeSession = chatSessions.find((s) => s.id === chatSessionId);
        if (activeSession?.personaId) {
          setExpandedPersonas(new Set([activeSession.personaId]));
        } else {
          // Expand first persona by default
          if (ps[0]) setExpandedPersonas(new Set([ps[0].id]));
        }
      } else if (ps?.[0]) {
        setExpandedPersonas(new Set([ps[0].id]));
      }
    });
    fetchChatSessions()
      .then((sessions) => dispatch({ type: "SET_CHAT_SESSIONS", sessions }))
      .catch((err) => console.error("Failed to load conversations:", err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function personaFor(id: string | null): Persona | null {
    return personas?.find((p) => p.id === id) ?? null;
  }

  function togglePersona(personaId: string) {
    setExpandedPersonas((prev) => {
      const next = new Set(prev);
      if (next.has(personaId)) next.delete(personaId);
      else next.add(personaId);
      return next;
    });
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

  // Group sessions by personaId
  const sessionsByPersona = new Map<string, typeof chatSessions>();
  const unknownSessions: typeof chatSessions = [];

  for (const s of chatSessions) {
    if (s.personaId) {
      const group = sessionsByPersona.get(s.personaId) ?? [];
      group.push(s);
      sessionsByPersona.set(s.personaId, group);
    } else {
      unknownSessions.push(s);
    }
  }

  // Ordered list of personas that have sessions, plus any with no sessions if loaded
  const personaList = personas ?? [];

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

        {/* Sessions grouped under their mentor */}
        {personaList.map((persona) => {
          const sessions = sessionsByPersona.get(persona.id) ?? [];
          if (sessions.length === 0) return null;
          const isExpanded = expandedPersonas.has(persona.id);
          const hasActive = sessions.some((s) => s.id === chatSessionId);

          return (
            <div key={persona.id}>
              {/* Mentor header row — click to expand/collapse */}
              <button
                type="button"
                onClick={() => togglePersona(persona.id)}
                className={`flex w-full items-center gap-sm border-b border-outline-variant/40 px-md py-sm text-left transition-colors hover:bg-surface-variant/30 ${
                  hasActive ? "bg-surface-container" : ""
                }`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-fixed-dim font-label-sm text-[13px] font-bold text-on-primary-container">
                  {initials(persona.name)}
                </div>
                <div className="flex flex-1 flex-col overflow-hidden">
                  <span className="truncate font-title-md text-sm font-semibold text-on-surface">
                    {persona.name}
                  </span>
                  <span className="text-[11px] text-on-surface-variant">
                    {sessions.length} {sessions.length === 1 ? "chat" : "chats"}
                  </span>
                </div>
                <Icon
                  name={isExpanded ? "expand_less" : "expand_more"}
                  size={20}
                  className="shrink-0 text-on-surface-variant"
                />
              </button>

              {/* Session rows under this mentor */}
              {isExpanded &&
                sessions.map((s) => {
                  const isActive = s.id === chatSessionId;
                  return (
                    <button
                      key={s.id}
                      onClick={() => openConversation(s.id)}
                      className={`flex w-full items-start gap-sm border-b border-outline-variant/20 py-sm pl-14 pr-md text-left transition-colors ${
                        isActive
                          ? "border-l-4 border-l-primary bg-surface-container"
                          : "hover:bg-surface-variant/30"
                      }`}
                    >
                      <div className="flex flex-1 flex-col overflow-hidden">
                        <div className="flex items-center justify-between">
                          <span className="truncate text-[12px] font-medium text-on-surface">
                            {s.lastMessagePreview
                              ? s.lastMessagePreview.slice(0, 30) + (s.lastMessagePreview.length > 30 ? "…" : "")
                              : "New conversation"}
                          </span>
                          <span className="ml-2 shrink-0 text-[10px] text-on-surface-variant">
                            {timeAgo(s.lastMessageAt)}
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })}
            </div>
          );
        })}

        {/* Sessions with no known persona */}
        {unknownSessions.map((s) => {
          const isActive = s.id === chatSessionId;
          return (
            <button
              key={s.id}
              onClick={() => openConversation(s.id)}
              className={`flex w-full items-center gap-md border-b border-outline-variant/30 p-md text-left transition-colors ${
                isActive ? "border-l-4 border-l-primary bg-surface-container" : "hover:bg-surface-variant/30"
              }`}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-container-high font-label-sm text-[13px] text-on-surface-variant">
                ?
              </div>
              <div className="flex flex-1 flex-col overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="truncate text-sm text-on-surface">Unknown mentor</span>
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
