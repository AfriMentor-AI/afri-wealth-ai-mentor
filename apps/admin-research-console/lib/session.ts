/**
 * Real email/password session for the Admin Research Console (card O4.2).
 *
 * Unlike frontend/lib/session.ts's silent per-device auto-provisioning (right
 * for an anonymous consumer PWA), this console is an internal tool restricted
 * to named admin/researcher/lead_architect accounts — it needs an actual
 * login screen and does not create accounts itself. Role enforcement lives
 * server-side (each service's _require_admin gate reads X-User-Roles from the
 * gateway-verified JWT); everything here is UX only, matching
 * docs/deployment/rbac-console-roles.md.
 */

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured;

  // When deployed (e.g. Vercel) with NEXT_PUBLIC_API_BASE_URL unset, fall
  // through to same-origin relative paths so next.config.js's rewrites()
  // proxy handles the request — a hardcoded localhost fallback would otherwise
  // make every deployed browser try to reach its own machine.
  if (typeof window !== "undefined") {
    const host = window.location.host;
    const isLocalhost = host === "localhost" || host.startsWith("localhost:") || host.startsWith("127.0.0.1");
    if (!isLocalhost) {
      return "";
    }
  }

  return "http://localhost:8000";
}

export const API_BASE = resolveApiBase();

const ACCESS_TOKEN_KEY = "admin-console-access-token";
const REFRESH_TOKEN_KEY = "admin-console-refresh-token";

export const CONSOLE_ROLES = ["admin", "researcher", "lead_architect"] as const;
export type ConsoleRole = (typeof CONSOLE_ROLES)[number];

interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

interface SessionUser {
  id: string;
  roles: string[];
}

function base64UrlDecode(segment: string): string {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return atob(padded);
}

function decodeUser(accessToken: string): SessionUser {
  const payload = JSON.parse(base64UrlDecode(accessToken.split(".")[1]));
  return { id: payload.sub as string, roles: (payload.roles as string[]) ?? [] };
}

function readStoredTokens(): TokenPair | null {
  if (typeof window === "undefined") return null;
  const accessToken = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  return accessToken && refreshToken ? { accessToken, refreshToken } : null;
}

function storeTokens(tokens: TokenPair): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function login(email: string, password: string): Promise<SessionUser> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error(res.status === 401 ? "Invalid email or password" : `Login failed: ${res.status}`);
  }
  const body = await res.json();
  storeTokens({ accessToken: body.access_token, refreshToken: body.refresh_token });
  return decodeUser(body.access_token);
}

/** Current session user from the stored access token, or null if signed out.
 * Does not refresh — call `apiFetch` for that; this is for render-time gating. */
export function currentUser(): SessionUser | null {
  const tokens = readStoredTokens();
  if (!tokens) return null;
  try {
    return decodeUser(tokens.accessToken);
  } catch {
    return null;
  }
}

export function hasConsoleRole(user: SessionUser | null): boolean {
  return !!user && user.roles.some((r) => (CONSOLE_ROLES as readonly string[]).includes(r));
}

async function refreshSession(): Promise<TokenPair> {
  const existing = readStoredTokens();
  if (!existing) throw new Error("No session to refresh");
  const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: existing.refreshToken }),
  });
  if (!res.ok) throw new Error("Session expired");
  const body = await res.json();
  return { accessToken: body.access_token, refreshToken: body.refresh_token };
}

/** fetch() against the gateway with the console session's bearer token
 * attached, refreshing once and retrying on a 401. Throws if there's no
 * session at all — callers should already have redirected to /login by then. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const tokens = readStoredTokens();
  if (!tokens) throw new Error("Not signed in");

  const attempt = async (accessToken: string) => {
    const user = decodeUser(accessToken);
    return fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
        Authorization: `Bearer ${accessToken}`,
        "X-User-Id": user.id,
      },
    });
  };

  let res = await attempt(tokens.accessToken);
  if (res.status === 401) {
    const refreshed = await refreshSession();
    storeTokens(refreshed);
    res = await attempt(refreshed.accessToken);
  }
  return res;
}
