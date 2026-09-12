"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { currentUser, hasConsoleRole } from "@/lib/session";

type GuardState = "checking" | "denied" | "ok";

/** Client-side route gate (card O4.2). This is UX only — the real
 * enforcement is server-side (_require_admin on every gated endpoint); a
 * user who bypasses this and calls the API directly without an allowed role
 * still gets a 403 from the backend. This just avoids showing the console's
 * chrome/empty widgets to someone who has no session or the wrong role. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<GuardState>("checking");

  useEffect(() => {
    const user = currentUser();
    if (!user) {
      router.replace("/login");
      return;
    }
    if (!hasConsoleRole(user)) {
      setState("denied");
      return;
    }
    setState("ok");
  }, [router]);

  if (state === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-on-surface-variant text-sm font-medium">
        <span className="material-symbols-outlined text-primary text-2xl animate-spin mr-2">sync</span>
        Loading Console…
      </div>
    );
  }
  if (state === "denied") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background text-center px-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-error-container text-error shadow-sm">
          <span className="material-symbols-outlined text-2xl">lock</span>
        </div>
        <p className="text-lg font-bold text-error">Access Restricted</p>
        <p className="max-w-sm text-xs text-on-surface-variant leading-relaxed">
          This console requires an <strong className="text-on-surface">admin</strong>,{" "}
          <strong className="text-on-surface">researcher</strong>, or{" "}
          <strong className="text-on-surface">lead_architect</strong> role. Please contact an engineering lead to
          grant access.
        </p>
        <button
          onClick={() => router.replace("/login")}
          className="mt-2 rounded-full border border-outline-variant bg-surface px-lg py-sm text-xs font-bold text-on-surface hover:bg-surface-variant transition-colors"
        >
          Back to Login
        </button>
      </div>
    );
  }
  return <>{children}</>;
}
