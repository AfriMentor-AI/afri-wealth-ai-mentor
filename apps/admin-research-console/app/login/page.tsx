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
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-outline-variant bg-surface p-8 shadow-xl"
      >
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-on-primary shadow-sm">
            <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              account_tree
            </span>
          </div>
          <div>
            <h1 className="font-headline font-bold text-lg text-primary leading-tight">AfriMentor</h1>
            <p className="font-label-sm text-[10px] uppercase tracking-widest text-on-surface-variant opacity-75">
              Research Console
            </p>
          </div>
        </div>

        <p className="mb-6 text-xs text-on-surface-variant">
          Sign in with an authorized <strong className="text-on-surface">admin</strong>,{" "}
          <strong className="text-on-surface">researcher</strong>, or{" "}
          <strong className="text-on-surface">lead_architect</strong> account.
        </p>

        <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
          Email
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="researcher@afrimentor.ai"
          className="mb-4 w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
        />

        <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
          Password
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="mb-6 w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
        />

        {error && (
          <div className="mb-4 rounded-xl border border-error/30 bg-error-container p-3 text-xs font-semibold text-on-error-container">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-full bg-primary py-2.5 text-sm font-bold text-on-primary shadow-xs hover:opacity-90 active:scale-98 transition-all disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in to Console"}
        </button>
      </form>
    </div>
  );
}
