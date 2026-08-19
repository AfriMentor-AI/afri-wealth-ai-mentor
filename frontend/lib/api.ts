// Re-export all mock implementations, then override the ones that have
// real backend implementations. This allows us to gradually migrate
// from mock to real APIs without breaking the app.
export * from "./mockApi";

import { apiFetch, getCurrentUserId } from "./session";
import type { ChatMessage, Commitment } from "./types";

interface BackendMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  is_commitment_candidate: boolean;
  citations: Array<{ label: string }>;
  created_at: string;
}

function toChatMessage(m: BackendMessage, userId: string): ChatMessage {
  return {
    id: m.id,
    userId,
    sender: m.role === "user" ? "user" : "mentor",
    content: m.content,
    citations: m.citations,
    is_commitment_candidate: m.is_commitment_candidate,
    created_at: m.created_at,
  };
}

/** GET /api/v1/chat/sessions/{id}/messages */
export async function fetchChatMessages(chatSessionId?: string): Promise<ChatMessage[]> {
  if (!chatSessionId) return [];
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages`);
  if (!res.ok) throw new Error(`fetchChatMessages failed: ${res.status}`);
  const body: BackendMessage[] = await res.json();
  const userId = await getCurrentUserId();
  return body.filter((m) => m.role !== "system").map((m) => toChatMessage(m, userId));
}

/** POST /api/v1/chat/sessions/{id}/messages — persists the user turn server-side
 * and returns the mentor's reply. */
export async function sendMessage(chatSessionId: string, text: string): Promise<ChatMessage> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content: text }),
  });
  if (!res.ok) throw new Error(`sendMessage failed: ${res.status}`);
  const body: BackendMessage = await res.json();
  return toChatMessage(body, await getCurrentUserId());
}

/** POST /api/v1/chat/sessions/{sessionId}/messages/{messageId}/tag */
export async function tagCommitment(chatSessionId: string, chatMessageId: string, goalId?: string): Promise<Commitment> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages/${chatMessageId}/tag`, {
    method: "POST",
    body: JSON.stringify({ goal_id: goalId }),
  });
  if (!res.ok) throw new Error(`tagCommitment failed: ${res.status}`);
  return (await res.json()) as Commitment;
}

/** POST /api/v1/chat/sessions — creates a new conversation and returns its id. */
export async function startChatSession(personaId?: string): Promise<string> {
  const res = await apiFetch("/api/v1/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ persona_id: personaId ?? null }),
  });
  if (!res.ok) throw new Error(`startChatSession failed: ${res.status}`);
  const body: { id: string } = await res.json();
  return body.id;
}

export interface ChatSessionSummary {
  id: string;
  personaId: string | null;
  lastMessagePreview: string | null;
  lastMessageAt: string | null;
  updatedAt: string;
}

interface BackendConversationSummary {
  id: string;
  persona_id: string | null;
  last_message_preview: string | null;
  last_message_at: string | null;
  updated_at: string;
}

/** GET /api/v1/chat/sessions — every conversation this user has started,
 * across mentors, newest activity first. Powers the multi-mentor
 * conversation list. */
export async function fetchChatSessions(): Promise<ChatSessionSummary[]> {
  const res = await apiFetch("/api/v1/chat/sessions");
  if (!res.ok) throw new Error(`fetchChatSessions failed: ${res.status}`);
  const body: BackendConversationSummary[] = await res.json();
  return body.map((s) => ({
    id: s.id,
    personaId: s.persona_id,
    lastMessagePreview: s.last_message_preview,
    lastMessageAt: s.last_message_at,
    updatedAt: s.updated_at,
  }));
}
