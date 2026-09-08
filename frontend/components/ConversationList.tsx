"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "./Icon";
import { archiveChatSession, fetchChatMessages, fetchChatSessions, fetchPersonas } from "@/lib/api";
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

function SessionRow({
  s,
  isActive,
  onOpen,
  onArchive,
}: {
  s: { id: string; lastMessagePreview: string | null; lastMessageAt: string | null };
  isActive: boolean;
  onOpen: () => void;
  onArchive: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [swipeX, setSwipeX] = useState(0);
  const touchStartX = useRef<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  function onTouchStart(e: React.TouchEvent) {
    touchStartX.current = e.touches[0].clientX;
  }
  function onTouchMove(e: React.TouchEvent) {
    if (touchStartX.current === null) return;
    const dx = e.touches[0].clientX - touchStartX.current;
    if (dx < 0) setSwipeX(Math.max(dx, -80));
  }
  function onTouchEnd() {
    if (swipeX < -50) {
      // Swiped far enough — show archive button revealed underneath
    } else {
      setSwipeX(0);
    }
    touchStartX.current = null;
  }

  const preview = s.lastMessagePreview
    ? s.lastMessagePreview.slice(0, 30) + (s.lastMessagePreview.length > 30 ? "…" : "")
    : "New conversation";

  return (
    <div className="relative">
      {/* Archive action revealed by swipe (mobile) — clipped to row bounds */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-y-0 right-0 flex w-20 items-center justify-center bg-error pointer-events-auto">
          <button
            type="button"
            aria-label="Archive"
            onClick={onArchive}
            className="flex flex-col items-center gap-[2px] text-on-error"
          >
            <Icon name="archive" size={20} />
            <span className="text-[10px]">Archive</span>
          </button>
        </div>
      </div>

      {/* Row — slides left on swipe */}
      <div
        style={{ transform: `translateX(${swipeX}px)`, transition: swipeX === 0 ? "transform 0.2s" : "none" }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        className={`group relative flex w-full items-start gap-sm border-b border-outline-variant/20 bg-surface py-sm pl-14 pr-md text-left transition-colors ${
          isActive ? "border-l-4 border-l-primary bg-surface-container" : "hover:bg-surface-variant/30"
        }`}
      >
        <button type="button" onClick={onOpen} className="flex flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="truncate text-[12px] font-medium text-on-surface">{preview}</span>
            <span className="ml-2 shrink-0 text-[10px] text-on-surface-variant">{timeAgo(s.lastMessageAt)}</span>
          </div>
        </button>

        {/* Desktop: ... menu on hover */}
        <div ref={menuRef} className="relative hidden shrink-0 group-hover:block">
          <button
            type="button"
            aria-label="More options"
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            className="flex items-center justify-center rounded-full p-[2px] text-on-surface-variant hover:bg-surface-container-high"
          >
            <Icon name="more_vert" size={16} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-6 z-20 min-w-[120px] rounded-md border border-outline-variant bg-surface-container shadow-md">
              <button
                type="button"
                onClick={() => { setMenuOpen(false); onArchive(); }}
                className="flex w-full items-center gap-sm px-md py-sm text-left font-body-md text-body-md text-on-surface hover:bg-surface-variant"
              >
                <Icon name="archive" size={16} />
                Archive
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ConversationList({ onSelect }: { onSelect?: () => void }) {
  const { chatSessions, chatSessionId } = useAppState();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);
  const [expandedPersonas, setExpandedPersonas] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchPersonas().then((ps) => {
      setPersonas(ps);
      if (ps && chatSessionId) {
        const activeSession = chatSessions.find((s) => s.id === chatSessionId);
        if (activeSession?.personaId) {
          setExpandedPersonas(new Set([activeSession.personaId]));
        } else if (ps[0]) {
          setExpandedPersonas(new Set([ps[0].id]));
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

  async function handleArchive(sessionId: string) {
    dispatch({ type: "REMOVE_CHAT_SESSION", sessionId });
    try {
      await archiveChatSession(sessionId);
    } catch (e) {
      console.error("Failed to archive session:", e);
      // Re-fetch to restore if the API call failed
      fetchChatSessions()
        .then((sessions) => dispatch({ type: "SET_CHAT_SESSIONS", sessions }))
        .catch(() => {});
    }
  }

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

        {personaList.map((persona) => {
          const sessions = sessionsByPersona.get(persona.id) ?? [];
          if (sessions.length === 0) return null;
          const isExpanded = expandedPersonas.has(persona.id);
          const hasActive = sessions.some((s) => s.id === chatSessionId);

          return (
            <div key={persona.id}>
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
                <Icon name={isExpanded ? "expand_less" : "expand_more"} size={20} className="shrink-0 text-on-surface-variant" />
              </button>

              {isExpanded &&
                sessions.map((s) => (
                  <SessionRow
                    key={s.id}
                    s={s}
                    isActive={s.id === chatSessionId}
                    onOpen={() => openConversation(s.id)}
                    onArchive={() => handleArchive(s.id)}
                  />
                ))}
            </div>
          );
        })}

        {unknownSessions.map((s) => (
          <SessionRow
            key={s.id}
            s={s}
            isActive={s.id === chatSessionId}
            onOpen={() => openConversation(s.id)}
            onArchive={() => handleArchive(s.id)}
          />
        ))}
      </div>
    </div>
  );
}
