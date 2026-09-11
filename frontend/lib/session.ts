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

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured;

  // In Codespaces, the frontend and gateway are usually exposed on different
  // forwarded ports under the same host slug. Derive the 8000 gateway URL from
  // the current app host so browser fetches stay reachable over HTTPS.
  if (typeof window !== "undefined") {
    const host = window.location.host;
    if (host.endsWith(".app.github.dev")) {
      const gatewayHost = host.replace(/-\d+\.app\.github\.dev$/, "-8000.app.github.dev");
      return `${window.location.protocol}//${gatewayHost}`;
    }

    // Only default to the local gateway when actually running on localhost.
    // Any other deployed host (e.g. Vercel) with NEXT_PUBLIC_API_BASE_URL unset
    // must fall through to same-origin relative paths so next.config.js's
    // rewrites() proxy handles the request — a hardcoded localhost fallback here
    // would otherwise make every deployed browser try to reach its own machine.
    const isLocalhost = host === "localhost" || host.startsWith("localhost:") || host.startsWith("127.0.0.1");
    if (!isLocalhost) {
      return "";
    }
  }

  return "http://localhost:8000";
}

const ACCESS_TOKEN_KEY = "afrimentor-access-token";
const REFRESH_TOKEN_KEY = "afrimentor-refresh-token";
const DEVICE_ID_KEY = "afrimentor-device-id";
const INTAKE_COMPLETED_KEY = "afrimentor-intake-completed";

interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

// In-memory cache so repeated calls within one page load don't keep re-reading
// localStorage; still backed by localStorage so it survives a reload.
let cachedAccessToken: string | null = null;

// Two independent hazards, one fix. (1) The backend rotates refresh tokens on
// every use (single-use — ADR-0001 §D5), so if two apiFetch calls hit a 401 at
// the same time and each independently calls refreshSession() with the same
// stored refresh token, only the first succeeds — the second's token is already
// revoked. (2) On a device's very first launch, several components mount and
// call apiFetch in parallel before any token exists, so each independently
// calls signupDeviceAccount() — the backend's exists-check-then-insert isn't
// atomic (auth-user-service `signup`), so concurrent signups for the same
// device email race into an unhandled 500 instead of a clean 409. Both are the
// same shape of bug: concurrent callers each mutating the shared token state
// instead of sharing one in-flight operation. A single lock around "obtain a
// valid token pair" (whichever operation gets there first) fixes both.
let pendingAuth: Promise<TokenPair> | null = null;

function withAuthLock(operation: () => Promise<TokenPair>): Promise<TokenPair> {
  if (!pendingAuth) {
    pendingAuth = operation().finally(() => {
      pendingAuth = null;
    });
  }
  return pendingAuth;
}

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

function deviceCredentials(): { email: string; password: string } {
  const deviceId = getDeviceId();
  // Password is the device id (a random UUID, 36 chars — well over the 8-char
  // minimum) so nothing user-meaningful is ever transmitted or stored as a secret.
  // Domain is `.app`, not `.local` — `.local`/`.test`/`.invalid`/etc. are IANA
  // special-use TLDs that email-validator (used by auth-user-service's EmailStr)
  // rejects outright, regardless of syntax.
  return { email: `${deviceId}@device.afrimentor.app`, password: deviceId };
}

async function signupDeviceAccount(): Promise<TokenPair> {
  const res = await fetch(`${resolveApiBase()}/api/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deviceCredentials()),
  });
  if (!res.ok) throw new Error(`device signup failed: ${res.status}`);
  const body = await res.json();
  return { accessToken: body.access_token, refreshToken: body.refresh_token };
}

/** Re-authenticates an existing device account by password (the device id is
 * deterministic and always available locally, independent of token state) —
 * this is the recovery path when the stored refresh token is dead but the
 * account itself is still there, e.g. it was revoked by a concurrent refresh,
 * or auth-user-service restarted and rotated its dev-mode signing key,
 * invalidating every outstanding token. */
async function loginDeviceAccount(): Promise<TokenPair> {
  const res = await fetch(`${resolveApiBase()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deviceCredentials()),
  });
  if (!res.ok) throw new Error(`device login failed: ${res.status}`);
  const body = await res.json();
  return { accessToken: body.access_token, refreshToken: body.refresh_token };
}

async function refreshSession(): Promise<TokenPair> {
  const existing = readStoredTokens();
  if (!existing) return signupDeviceAccount();

  const res = await fetch(`${resolveApiBase()}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: existing.refreshToken }),
  });
  if (res.ok) {
    const body = await res.json();
    return { accessToken: body.access_token, refreshToken: body.refresh_token };
  }
  // Refresh token expired/revoked. The account usually still exists — log back in
  // with this device's deterministic credentials rather than jumping straight to
  // signup, which 409s (and strands the device with no valid session at all) if
  // the account is already registered. Only signup if login says the account is
  // genuinely gone (e.g. deactivated).
  try {
    return await loginDeviceAccount();
  } catch {
    return signupDeviceAccount();
  }
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
  const fresh = await withAuthLock(signupDeviceAccount);
  storeTokens(fresh);
  return fresh.accessToken;
}

/** Whether this device has a stored device id — i.e. has at least been
 * provisioned/visited before. NOTE: this alone does NOT mean intake was done;
 * a device id is written the moment the first authenticated request runs
 * (which can happen mid-intake). Use `isIntakeCompleted()` for the intake gate. */
export function isDeviceProvisioned(): boolean {
  if (typeof window === "undefined") return false;
  return !!window.localStorage.getItem(DEVICE_ID_KEY);
}

/** Marks intake as completed on this device. Set once, after the intake
 * submission succeeds server-side, and stays set across reloads/app-closes so
 * a user who completed intake is never pushed back through it. */
export function markIntakeCompleted(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(INTAKE_COMPLETED_KEY, "1");
}

/** True once intake has been completed on this device. This is the single
 * source of truth the landing/routing code should use to decide between
 * "Continue to chat" and "Get started (intake)". */
export function isIntakeCompleted(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(INTAKE_COMPLETED_KEY) === "1";
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
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  const attempt = async (accessToken: string) => {
    const userId = await getCurrentUserId();
    return fetch(`${resolveApiBase()}${path}`, {
      ...init,
      headers: {
        ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
        Authorization: `Bearer ${accessToken}`,
        "X-User-Id": userId,
      },
    });
  };

  const token = await ensureAccessToken();
  let res = await attempt(token);
  if (res.status === 401) {
    const refreshed = await withAuthLock(refreshSession);
    storeTokens(refreshed);
    res = await attempt(refreshed.accessToken);
  }
  return res;
}