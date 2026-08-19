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
    return <div className="flex min-h-screen items-center justify-center text-on-surface-dim">Loading…</div>;
  }
  if (state === "denied") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center">
        <p className="text-lg font-semibold text-danger">Access denied</p>
        <p className="max-w-sm text-sm text-on-surface-dim">
          This console is restricted to admin, researcher, or lead_architect accounts. Ask a
          lead to grant your account one of these roles.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
