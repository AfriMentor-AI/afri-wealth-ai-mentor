"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppState } from "@/lib/store";
import { NotificationPopover } from "@/components/NotificationPopover";
import { ThemeSwitch, ThemeToggleButton } from "@/components/ThemeSwitch";

export const NAV = [
  { href: "/chat", label: "Chat", icon: "chat_bubble", mIcon: "forum" },
  { href: "/goals", label: "Goals", icon: "flag", mIcon: "flag" },
  { href: "/library", label: "Library", icon: "auto_stories", mIcon: "local_library" },
  { href: "/progress", label: "Progress", icon: "query_stats", mIcon: "trending_up" },
] as const;

const ACTIVE = "relative bg-primary-container/10 text-primary-container font-semibold before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:bg-sunburst-gold before:rounded-r";

export function KenteStrip() {
  return (
    <div className="flex h-1 w-full">
      <div className="h-full flex-1 bg-sunburst-gold" />
      <div className="h-full flex-1 bg-primary-container" />
      <div className="h-full flex-1 bg-tertiary" />
      <div className="h-full flex-1 bg-midnight-bg" />
      <div className="h-full flex-1 bg-secondary" />
    </div>
  );
}

/** The 240px navigation sidebar used on every screen except Chat (which has its own rail). */
export function AppSidebar() {
  const pathname = usePathname() || "";
  const { profile } = useAppState();
  return (
    <aside className="fixed left-0 top-0 z-50 hidden h-screen w-[240px] select-none flex-col justify-between border-r border-outline-subtle bg-surface-low md:flex">
      <div className="w-full">
        <KenteStrip />
        <div className="px-5 pb-5 pt-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-sunburst-gold bg-paper shadow-sm">
              <span className="material-symbols-outlined text-[20px] text-primary-container">flight</span>
            </div>
            <div className="flex flex-col">
              <span className="font-headline-lg-mobile text-[26px] font-medium leading-7 tracking-tight text-primary-container">AfriMentor</span>
              <span className="mt-0.5 font-eyebrow text-eyebrow uppercase tracking-widest text-outline-strong">Dignified Growth</span>
            </div>
          </Link>
        </div>
        <nav className="mt-2 flex flex-col gap-1 px-3" aria-label="Primary">
          {NAV.map((n) => {
            const on = pathname === n.href || pathname.startsWith(n.href + "/");
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={on ? "page" : undefined}
                className={`flex h-[52px] items-center gap-3 rounded-lg px-3 transition-all duration-150 ${on ? ACTIVE : "font-body-md text-body-md text-on-surface-variant hover:bg-surface-high hover:text-on-surface"}`}
              >
                <span className={`material-symbols-outlined text-[24px] ${on ? "icon-fill" : ""}`}>{n.icon}</span>
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="border-t border-outline-subtle bg-surface-low p-4">
        <div className="mb-4 flex items-center justify-between">
          <NotificationPopover placement="below-right" buttonClassName="relative p-2 rounded-lg text-on-surface-variant hover:bg-surface-high hover:text-on-surface transition-colors" iconSize={22} />
          <ThemeSwitch />
        </div>
        <div className="flex items-center gap-3 pt-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary">
            <span className="material-symbols-outlined text-[18px] text-on-primary">person</span>
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-label-sm text-label-sm text-on-surface">{profile?.name || "Your profile"}</span>
            <span className="truncate font-caption text-caption text-outline-strong">{profile?.location || "AfriMentor member"}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

/** Mobile header + bottom tab bar (m7 pattern). `title` is the screen name. */
export function MobileChrome({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <header className="fixed inset-x-0 top-0 z-50 bg-surface/85 pt-safe shadow-[0_1px_8px_rgba(20,17,13,0.03)] backdrop-blur-xl md:hidden">
      <div className="flex h-16 items-center justify-between px-margin">
        <div className="flex items-center gap-space-sm">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-default text-primary">
            <span className="material-symbols-outlined text-[20px]">temp_preferences_custom</span>
          </div>
          <div>
            <span className="block font-eyebrow text-eyebrow uppercase tracking-widest text-primary">AfriMentor</span>
            <h1 className="font-title-md text-title-md leading-none tracking-tight text-on-surface">{title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-space-sm">
          {right}
          <NotificationPopover placement="below-right" buttonClassName="relative flex h-11 w-11 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface transition-colors" ringClassName="ring-surface" iconSize={22} />
          <ThemeToggleButton />
        </div>
      </div>
    </header>
  );
}

export function MobileTabs() {
  const pathname = usePathname() || "";
  return (
    <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-50 bg-surface/90 pb-safe shadow-[0_-4px_20px_rgba(20,17,13,0.04)] backdrop-blur-xl md:hidden">
      <div className="flex items-center justify-center pb-0.5 pt-1.5">
        <span className="font-eyebrow text-[9px] uppercase tracking-widest text-outline-strong opacity-75">Dignified Growth</span>
      </div>
      <div className="flex h-16 items-center justify-around px-gutter">
        {NAV.map((n) => {
          const on = pathname === n.href || pathname.startsWith(n.href + "/");
          return (
            <Link key={n.href} href={n.href} aria-current={on ? "page" : undefined}
              className={`relative flex min-h-[44px] min-w-[56px] flex-col items-center justify-center gap-0.5 transition-colors ${on ? "font-semibold text-primary" : "text-on-surface-variant hover:text-primary"}`}>
              <span className={`material-symbols-outlined text-[24px] ${on ? "icon-fill" : ""}`}>{n.mIcon}</span>
              <span className="font-caption text-caption">{n.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/** Wrapper for non-chat screens: sidebar on ≥md, header + tabs below. */
export function AppFrame({ title, children, mobileRight, contentClassName = "" }: { title: string; children: React.ReactNode; mobileRight?: React.ReactNode; contentClassName?: string }) {
  return (
    <div className="min-h-screen bg-warm-white text-on-surface">
      <AppSidebar />
      <MobileChrome title={title} right={mobileRight} />
      <div className={`min-h-screen pb-28 pt-16 md:pb-0 md:pl-[240px] md:pt-0 ${contentClassName}`}>{children}</div>
      <MobileTabs />
    </div>
  );
}
