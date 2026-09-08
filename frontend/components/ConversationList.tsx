"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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

function ArchiveConfirmDialog({
  preview,
  onConfirm,
  onCancel,
}: {
  preview: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  // Trap focus & close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 px-md backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-2xl bg-surface p-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Icon */}
        <div className="mb-md flex justify-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-secondary-container">
            <Icon name="archive" size={28} className="text-secondary" />
          </div>
        </div>

        {/* Title */}
        <h2 className="mb-sm text-center font-title-lg text-title-lg text-on-surface">
          Archive this chat?
        </h2>

        {/* Preview */}
        <p className="mb-xs text-center font-body-md text-body-md text-on-surface-variant">
          &ldquo;{preview}&rdquo;
        </p>
        <p className="mb-lg text-center font-body-sm text-body-sm text-on-surface-variant">
          This chat will be hidden from your list. Your commitments and goals linked to it are kept safe.
        </p>

        {/* Actions */}
        <div className="flex gap-sm">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-full border border-outline py-sm font-label-lg text-label-lg text-on-surface transition-colors hover:bg-surface-variant active:scale-95"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 rounded-full bg-secondary py-sm font-label-lg text-label-lg text-on-secondary transition-colors hover:bg-secondary/90 active:scale-95"
          >
            Archive
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
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
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);
  const [swipeX, setSwipeX] = useState(0);
  const touchStartX = useRef<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

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
      // reveal stays — tap the red button to confirm
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
      {/* Swipe-reveal layer (mobile) */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="pointer-events-auto absolute inset-y-0 right-0 flex w-20 items-center justify-center bg-error">
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

      {/* Row */}
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
            ref={btnRef}
            onClick={(e) => {
              e.stopPropagation();
              if (!menuOpen && btnRef.current) {
                const r = btnRef.current.getBoundingClientRect();
                setMenuPos({ top: r.bottom + 4, right: window.innerWidth - r.right });
              }
              setMenuOpen((v) => !v);
            }}
            className="flex items-center justify-center rounded-full p-[2px] text-on-surface-variant hover:bg-surface-container-high"
          >
            <Icon name="more_vert" size={16} />
          </button>
          {menuOpen && menuPos && createPortal(
            <div
              ref={menuRef}
              style={{ position: "fixed", top: menuPos.top, right: menuPos.right, zIndex: 9998 }}
              className="min-w-[120px] rounded-md border border-outline-variant bg-surface-container shadow-md"
            >
              <button
                type="button"
                onClick={() => { setMenuOpen(false); onArchive(); }}
                className="flex w-full items-center gap-sm px-md py-sm text-left font-body-md text-body-md text-on-surface hover:bg-surface-variant"
              >
                <Icon name="archive" size={16} />
                Archive
              </button>
            </div>,
            document.body,
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
  const [pendingArchive, setPendingArchive] = useState<{ id: string; preview: string } | null>(null);

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

  function requestArchive(sessionId: string, preview: string) {
    setPendingArchive({ id: sessionId, preview });
  }

  async function confirmArchive() {
    if (!pendingArchive) return;
    const { id } = pendingArchive;
    setPendingArchive(null);
    dispatch({ type: "REMOVE_CHAT_SESSION", sessionId: id });
    try {
      await archiveChatSession(id);
    } catch (e) {
      console.error("Failed to archive session:", e);
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
                    onArchive={() => requestArchive(s.id, s.lastMessagePreview?.slice(0, 40) ?? "New conversation")}
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
            onArchive={() => requestArchive(s.id, s.lastMessagePreview?.slice(0, 40) ?? "New conversation")}
          />
        ))}
      </div>

      {pendingArchive && (
        <ArchiveConfirmDialog
          preview={pendingArchive.preview}
          onConfirm={confirmArchive}
          onCancel={() => setPendingArchive(null)}
        />
      )}
    </div>
  );
}
