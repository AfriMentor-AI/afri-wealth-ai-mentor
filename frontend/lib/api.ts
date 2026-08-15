// Re-export all mock implementations, then override the ones that have
// real backend implementations. This allows us to gradually migrate
// from mock to real APIs without breaking the app.
export * from "./mockApi";

import { mockChatMessages } from "./mockData";
import { apiFetch, getCurrentUserId } from "./session";
import type { ChatMessage, Commitment } from "./types";

async function fetchJsonWithFallback<T>(path: string, fallback: T, init: RequestInit = {}): Promise<T> {
  try {
    const res = await apiFetch(path, init);
    if (!res.ok) {
      console.warn(`[api] ${path} failed with ${res.status}; using mock fallback`, res);
      return fallback;
    }
    return (await res.json()) as T;
  } catch (error) {
    console.warn(`[api] ${path} unavailable; using mock fallback`, error);
    return fallback;
  }
}

/**
 * GET /v1/chat/sessions/{sessionId}/messages
 *
 * The real endpoint will eventually need a session ID. For now, we allow
 * callers to omit it to fetch a default/global firehose of messages.
 */
export async function fetchChatMessages(opts?: { sessionId?: string } | string): Promise<ChatMessage[]> {
  const sessionId = typeof opts === "string" ? opts : opts?.sessionId;
  if (!sessionId) {
    return [];
  }

  const path = `/api/v1/chat/sessions/${sessionId}/messages`;
  return fetchJsonWithFallback(path, mockChatMessages);
}

/**
 * POST /v1/chat/sessions/{sessionId}/messages
 */
export async function sendMessage(chatSessionId: string, text: string): Promise<ChatMessage>;
export async function sendMessage(input: { text: string; personaId?: string }): Promise<ChatMessage>;
export async function sendMessage(
  a: string | { text: string; personaId?: string },
  b?: string
): Promise<ChatMessage> {
  // The UI calls this with different shapes. The backend endpoint needs a
  // session ID. For now, we'll start a new session if one isn't provided.
  let sessionId: string;
  let messageText: string;

  if (typeof a === "string") {
    sessionId = a;
    messageText = b ?? "";
  } else {
    sessionId = await startChatSession(a.personaId);
    messageText = a.text;
  }

  const userId = await getCurrentUserId();
  const res = await apiFetch(`/api/v1/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content: messageText, user_id: userId }),
  });
  if (!res.ok) throw new Error(`sendMessage failed: ${res.status}`);
  return (await res.json()) as ChatMessage;
}

/**
 * POST /v1/chat/sessions/{sessionId}/messages/{messageId}/tag
 */
export async function tagCommitment(chatSessionId: string, chatMessageId: string, goalId?: string): Promise<Commitment> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages/${chatMessageId}/tag`, {
    method: "POST",
    body: JSON.stringify({ goal_id: goalId }),
  });
  if (!res.ok) throw new Error(`tagCommitment failed: ${res.status}`);
  return (await res.json()) as Commitment;
}

/**
 * POST /v1/chat/sessions
 */
export async function startChatSession(personaId?: string): Promise<string> {
  const res = await apiFetch("/api/v1/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ persona_id: personaId }),
  });
  if (!res.ok) throw new Error(`startChatSession failed: ${res.status}`);
  const body = await res.json();
  return body.id as string;
}