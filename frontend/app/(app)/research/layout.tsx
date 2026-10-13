"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";

const TABS = [
  { label: "Personas", icon: "psychology", href: "/research/personas" },
  { label: "RAG corpus", icon: "folder_shared", href: "/research/rag-corpus" },
];

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <AppFrame title="Research console">
      <KenteStrip />
      <div className="border-b border-outline-variant bg-surface-container-low px-5 pt-5 md:px-10">
        <p className="font-eyebrow text-eyebrow uppercase text-on-surface-variant"><span className="text-sunburst-gold">●</span> Evaluation cockpit</p>
        <h1 className="mt-1 font-title-md text-[28px] leading-9 text-on-surface">Researcher console</h1>
        <nav className="mt-4 flex gap-1" aria-label="Console">
          {TABS.map((t) => {
            const on = pathname === t.href || pathname?.startsWith(t.href + "/");
            return (
              <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined} className={`flex items-center gap-2 rounded-t-xl px-5 py-3 font-label-sm text-[15px] transition-colors ${on ? "bg-surface text-primary shadow-[0_2px_0_0_rgb(var(--c-sunburst-gold))]" : "text-on-surface-variant hover:bg-surface-container"}`}>
                <Icon name={t.icon} size={20} filled={on} /> {t.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="min-w-0">{children}</div>
    </AppFrame>
  );
}
