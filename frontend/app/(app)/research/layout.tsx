"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";

const NAV_ITEMS = [
  { label: "Personas", icon: "person", href: "/research/personas" },
  { label: "RAG Corpus", icon: "folder_shared", href: "/research/rag-corpus" },
  { label: "Analytics", icon: "analytics", href: "/research/analytics" },
  { label: "Settings", icon: "settings", href: "/research/settings" },
];

export default function ResearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    // h-full fills the flex content area given by app/(app)/layout.tsx
    <div className="flex h-full overflow-hidden bg-[#F1F4F9] text-on-surface">
      {/* ------------------------------------------------------------------
          Persistent Research Console sidebar
          No `hidden md:flex` — always visible. The console is a desktop-first
          admin tool; the main app BottomTabNav (which is already `md:flex-row`)
          handles top-level routing, so a persistent second sidebar here is fine.
      ------------------------------------------------------------------ */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-outline-variant bg-surface">
        {/* Logo / brand */}
        <div className="px-lg py-xl">
          <h1 className="font-headline-lg text-headline-lg tracking-tighter text-primary">
            AfriMentor
          </h1>
          <p className="mt-xs font-label-sm text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
            Console
          </p>
        </div>

        {/* Nav items */}
        <nav className="flex-1 space-y-xs px-md" aria-label="Console">
          {NAV_ITEMS.map(({ label, icon, href }) => {
            const isActive =
              pathname === href || pathname?.startsWith(href + "/");
            return (
              <Link
                key={label}
                href={href}
                className={`flex items-center gap-md rounded-full px-md py-sm font-semibold transition-all ${
                  isActive
                    ? "bg-secondary-container text-on-secondary-container"
                    : "text-on-surface-variant hover:bg-surface-variant"
                }`}
              >
                <Icon name={icon} filled={isActive} size={20} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Profile footer */}
        <div className="mt-auto border-t border-outline-variant p-lg">
          <div className="flex items-center gap-md">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-primary bg-surface-container">
              <Icon name="person" size={22} className="text-on-surface-variant" />
            </div>
            <div>
              <p className="font-bold leading-tight text-on-surface">
                Kofi Mensah
              </p>
              <p className="text-xs text-on-surface-variant">Lead Architect</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Page content — fills remaining width, manages its own scroll */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
