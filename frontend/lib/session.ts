/**
 * Device-scoped session against the real API gateway (card O2.4).
 *
 * AfriMentor has no login screen by design — per the Stitch design export the flow is
 * Splash -> Intake -> Persona -> app, with no account-creation step shown to the user
 * (the target user is smartphone-only, low-bandwidth, low-literacy; a login form
 * before any value is shown would be exactly the wrong friction). So instead of a
 * login UI, the app silently provisions one auth-user-service account per device on
 * first launch (POST /auth/signup with a random, locally-generated device id as the
 * "identity"), stores the resulting tokens, and reuses/refreshes them on every later
 * visit. This is a deliberate scoping decision for O2.4's three screens, not a stand-in
 * for a real login/signup flow — flagging here in case that gets revisited.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "afrimentor-access-token";
const REFRESH_TOKEN_KEY = "afrimentor-refresh-token";
const DEVICE_ID_KEY = "afrimentor-device-id";

interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

// In-memory cache so repeated calls within one page load don't keep re-reading
// localStorage; still backed by localStorage so it survives a reload.
let cachedAccessToken: string | null = null;

function getDeviceId(): string {
  let id = window.localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

function readStoredTokens(): TokenPair | null {
  const accessToken = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  return accessToken && refreshToken ? { accessToken, refreshToken } : null;
}

function storeTokens(tokens: TokenPair): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
  cachedAccessToken = tokens.accessToken;
}

async function signupDeviceAccount(): Promise<TokenPair> {
  const deviceId = getDeviceId();
  const res = await fetch(`${API_BASE}/api/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Password is the device id (a random UUID, 36 chars — well over the 8-char
    // minimum) so nothing user-meaningful is ever transmitted or stored as a secret.
    // Domain is `.app`, not `.local` — `.local`/`.test`/`.invalid`/etc. are IANA
    // special-use TLDs that email-validator (used by auth-user-service's EmailStr)
    // rejects outright, regardless of syntax.
    body: JSON.stringify({
      email: `${deviceId}@device.afrimentor.app`,
      password: deviceId,
    }),
  });
  if (!res.ok) throw new Error(`device signup failed: ${res.status}`);
  const body = await res.json();
  return { accessToken: body.access_token, refreshToken: body.refresh_token };
}

async function refreshSession(): Promise<TokenPair> {
  const existing = readStoredTokens();
  if (existing) {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: existing.refreshToken }),
    });
    if (res.ok) {
      const body = await res.json();
      return { accessToken: body.access_token, refreshToken: body.refresh_token };
    }
    // Refresh token expired/revoked (e.g. account deactivated, or this is a stale
    // token from a previous local dev database) — fall through to a fresh signup.
  }
  return signupDeviceAccount();
}

/** Returns a currently-valid access token, provisioning/refreshing the device
 * session as needed. Safe to call on every request that needs auth. */
async function ensureAccessToken(): Promise<string> {
  if (cachedAccessToken) return cachedAccessToken;
  const existing = readStoredTokens();
  if (existing) {
    cachedAccessToken = existing.accessToken;
    return cachedAccessToken;
  }
  const fresh = await signupDeviceAccount();
  storeTokens(fresh);
  return fresh.accessToken;
}

/** JWT segments are base64url (`-`/`_`, unpadded), not plain base64 — `atob()`
 * alone mis-decodes any segment containing those characters, which most will. */
function base64UrlDecode(segment: string): string {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return atob(padded);
}

/** Returns this device's user id (the JWT's `sub` claim), decoded locally —
 * no network call needed since the gateway already verifies the token. */
export async function getCurrentUserId(): Promise<string> {
  const token = await ensureAccessToken();
  const payload = JSON.parse(base64UrlDecode(token.split(".")[1]));
  return payload.sub as string;
}

/** fetch() against the gateway with the device session's bearer token attached,
 * transparently refreshing once and retrying on a 401. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = async (accessToken: string) =>
    fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
        Authorization: `Bearer ${accessToken}`,
      },
    });

  const token = await ensureAccessToken();
  let res = await attempt(token);
  if (res.status === 401) {
    const refreshed = await refreshSession();
    storeTokens(refreshed);
    res = await attempt(refreshed.accessToken);
  }
  return res;
}
