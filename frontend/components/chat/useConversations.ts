"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteChatSession, fetchChatMessages, fetchChatSessions, fetchPersonas, type ChatSessionSummary } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { useAppDispatch, useAppState } from "@/lib/store";
import { mentorFor, type MentorMeta } from "@/lib/mentors";

export interface ConversationRow {
  session: ChatSessionSummary;
  persona: Persona | null;
  mentor: MentorMeta;
  title: string;
  preview: string;
}

export function timeAgo(iso: string | null, short = false): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return short ? "now" : "Just now";
  if (mins < 60) return short ? `${mins}m` : `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return short ? `${hours}h` : `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return short ? "Yday" : "Yesterday";
  if (days < 7) return short ? `${days}d` : `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Shared data + actions for every conversation list layout (panel, drawer, mobile screen). */
export function useConversations() {
  const { chatSessions, chatSessionId } = useAppState();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; preview: string } | null>(null);

  useEffect(() => {
    let alive = true;
    fetchPersonas().then((ps) => alive && setPersonas(ps)).catch(() => {});
    fetchChatSessions()
      .then((sessions) => { if (alive) dispatch({ type: "SET_CHAT_SESSIONS", sessions }); })
      .catch((err) => console.error("Failed to load conversations:", err))
      .finally(() => alive && setLoaded(true));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows: ConversationRow[] = useMemo(() => {
    const sorted = [...chatSessions].sort((a, b) => +new Date(b.lastMessageAt ?? b.updatedAt) - +new Date(a.lastMessageAt ?? a.updatedAt));
    return sorted.map((s) => {
      const persona = personas?.find((p) => p.id === s.personaId) ?? null;
      const mentor = mentorFor(persona ?? (s.personaId ? { id: s.personaId } : null));
      return { session: s, persona, mentor, title: mentor.name, preview: s.lastMessagePreview?.trim() || "Starting a new conversation…" };
    });
  }, [chatSessions, personas]);

  const open = useCallback(async (sessionId: string) => {
    if (sessionId !== chatSessionId) {
      dispatch({ type: "SET_CHAT_SESSION_ID", sessionId });
      const s = chatSessions.find((x) => x.id === sessionId);
      const persona = personas?.find((p) => p.id === s?.personaId) ?? null;
      if (persona) dispatch({ type: "SET_PERSONA", persona });
      dispatch({ type: "SET_CHAT_MESSAGES", messages: [] });
      const messages = await fetchChatMessages(sessionId);
      dispatch({ type: "SET_CHAT_MESSAGES", messages });
    }
  }, [chatSessionId, chatSessions, personas, dispatch]);

  async function confirmDelete() {
    if (!pendingDelete) return;
    const { id } = pendingDelete;
    setPendingDelete(null);
    dispatch({ type: "REMOVE_CHAT_SESSION", sessionId: id });
    try {
      await deleteChatSession(id);
    } catch (e) {
      console.error("Failed to delete session:", e);
      fetchChatSessions().then((sessions) => dispatch({ type: "SET_CHAT_SESSIONS", sessions })).catch(() => {});
    }
  }

  return {
    rows, personas, loaded, activeId: chatSessionId, open,
    pendingDelete, requestDelete: (id: string, preview: string) => setPendingDelete({ id, preview }),
    cancelDelete: () => setPendingDelete(null), confirmDelete,
  };
}

export type Conversations = ReturnType<typeof useConversations>;
