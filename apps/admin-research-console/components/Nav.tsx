"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearSession } from "@/lib/session";

const links = [
  { href: "/corpus-admin", label: "RAG Corpus Admin" },
  { href: "/dashboard", label: "Persona Consistency" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav className="flex items-center justify-between border-b border-border bg-surface-raised px-6 py-3">
      <div className="flex items-center gap-6">
        <span className="text-sm font-semibold tracking-wide text-accent">AfriMentor Research Console</span>
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`text-sm ${pathname === l.href ? "text-on-surface font-medium" : "text-on-surface-dim hover:text-on-surface"}`}
          >
            {l.label}
          </Link>
        ))}
      </div>
      <button
        onClick={() => {
          clearSession();
          router.replace("/login");
        }}
        className="text-sm text-on-surface-dim hover:text-on-surface"
      >
        Sign out
      </button>
    </nav>
  );
}
