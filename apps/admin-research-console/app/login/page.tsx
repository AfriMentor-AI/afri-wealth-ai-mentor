"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, hasConsoleRole } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(email, password);
      if (!hasConsoleRole(user)) {
        setError("This account has no admin/researcher/lead_architect role.");
        return;
      }
      router.replace("/corpus-admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-md border border-border bg-surface-raised p-8"
      >
        <h1 className="mb-1 text-lg font-semibold">Research Console</h1>
        <p className="mb-6 text-sm text-on-surface-dim">Admin / researcher / lead architect sign-in</p>

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-on-surface-dim">
          Email
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
        />

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-on-surface-dim">
          Password
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
        />

        {error && <p className="mb-4 text-sm text-danger">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-accent py-2 text-sm font-semibold text-on-accent disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
