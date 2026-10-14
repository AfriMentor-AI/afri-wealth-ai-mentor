"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { img } from "@/lib/stitchImages";
import { useAppState } from "@/lib/store";
import { NotificationPopover } from "@/components/NotificationPopover";
import { ThemeSwitch } from "@/components/ThemeSwitch";
import { KenteStrip } from "@/components/shell/AppSidebar";

const RAIL = [
  { href: "/chat", icon: "chat", title: "Chat" },
  { href: "/goals", icon: "target", title: "Goals and milestones" },
  { href: "/library", icon: "auto_stories", title: "Library" },
  { href: "/progress", icon: "query_stats", title: "Progress" },
];

export function Initial({ className = "" }: { className?: string }) {
  const { profile } = useAppState();
  const letter = (profile?.name || "A").trim().charAt(0).toUpperCase();
  return <span className={`flex items-center justify-center rounded-full bg-primary font-label-sm font-bold text-on-primary ${className}`} aria-hidden>{letter}</span>;
}

/** 72px icon rail, only on the Chat screen (W1/W2). */
export function ChatRail() {
  const pathname = usePathname() || "";
  return (
    <aside className="fixed bottom-0 left-0 top-0 z-50 hidden w-[72px] select-none flex-col items-center justify-between bg-surface-low shadow-[0_1px_8px_rgba(0,0,0,0.04)] md:flex">
      <div className="flex w-full flex-col items-center">
        <KenteStrip />
        <Link href="/" aria-label="AfriMentor home" className="flex items-center justify-center pb-space-lg pt-space-md">
          <div className="relative flex h-11 w-11 items-center justify-center rounded-full bg-gold-mist/40 ring-2 ring-sunburst-gold/60">
            <img src={img("i_EIZNdX3bmq9vgcMQ")} alt="AfriMentor" className="h-8 w-auto object-contain" />
          </div>
        </Link>
        <nav aria-label="Primary" className="flex w-full flex-col items-center gap-space-sm px-space-xs">
          {RAIL.map((n) => {
            const on = pathname === n.href || pathname.startsWith(n.href + "/");
            return (
              <Link key={n.href} href={n.href} title={n.title} aria-label={n.title} aria-current={on ? "page" : undefined}
                className={`relative flex h-12 w-12 items-center justify-center rounded-xl transition-all ${on ? "bg-primary-container text-on-primary shadow-sm" : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"}`}>
                <span className={`material-symbols-outlined text-[24px] ${on ? "icon-fill" : ""}`}>{n.icon}</span>
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="flex w-full flex-col items-center gap-space-md pb-space-lg">
        <NotificationPopover placement="right-bottom" buttonClassName="relative flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-surface-container-high hover:text-on-surface" iconSize={22} />
        <ThemeSwitch vertical />
        <div className="pt-space-xs"><Initial className="h-8 w-8 text-[13px] ring-1 ring-outline-variant" /></div>
      </div>
    </aside>
  );
}

export function ChatTopBar() {
  return (
    <header className="fixed left-0 right-0 top-0 z-40 hidden h-16 items-center justify-between bg-surface/90 px-4 backdrop-blur-xl md:left-[72px] md:flex lg:px-8">
      <div className="flex items-center gap-space-sm">
        <span className="font-eyebrow text-eyebrow uppercase tracking-widest text-primary">AfriMentor AI</span>
        <span className="h-1 w-1 rounded-full bg-outline-strong" />
        <span className="font-caption text-caption text-on-surface-variant">Mentor salon</span>
      </div>
      <div className="flex items-center gap-space-md">
        <div className="hidden items-center gap-space-xs rounded-full bg-gold-mist px-3 py-1.5 sm:flex">
          <span className="material-symbols-outlined icon-fill text-[16px] text-sunburst-gold">verified</span>
          <span className="font-caption text-caption font-medium text-on-surface">Mentors online</span>
        </div>
        <Initial className="h-8 w-8 text-[13px] ring-1 ring-outline-subtle" />
      </div>
    </header>
  );
}
