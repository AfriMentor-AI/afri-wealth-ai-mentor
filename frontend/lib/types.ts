/**
 * G1.3: this file is now a thin re-export of the shared frontend/backend
 * contract at contract/types.ts, kept so existing `@/lib/types` imports
 * across the app don't all need to change. The contract module is the
 * actual source of truth — edit shapes there, not here.
 */
export * from "../contract/types";

// Legacy alias: earlier code referred to this as ThemeName. Not part of
// the shared API contract (it's a pure frontend/UI concern), so it lives
// here instead of in contract/types.ts.
export type ThemeName = "heritage" | "nocturnal";
