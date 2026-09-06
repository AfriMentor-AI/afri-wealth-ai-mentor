"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";
import { NotificationPopover } from "./NotificationPopover";

const tabs = [
  { href: "/chat", label: "Chat", icon: "chat_bubble" },
  { href: "/goals", label: "Goals", icon: "target" },
  { href: "/library", label: "Library", icon: "auto_stories" },
  { href: "/progress", label: "Progress", icon: "query_stats" },
];

// Moved from a bottom tab bar to a fixed top-left cluster per request.
// Note: bottom nav is the standard mobile pattern specifically for
// one-handed thumb reach — this trades that away for a consistent
// top-left position across breakpoints, which was the explicit ask.
export function TopNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed left-0 top-0 z-20 flex items-center gap-xs overflow-x-auto rounded-br-lg border-b border-r border-outline-variant bg-surface px-sm py-xs shadow-sm md:gap-1 md:px-md md:py-sm"
      aria-label="Main"
    >
      {tabs.map(({ href, label, icon }) => {
        const isActive = pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={`tap-target flex shrink-0 flex-col items-center gap-0.5 rounded px-sm py-xs transition-colors duration-150 active:scale-90 md:flex-row md:gap-2 md:px-md md:py-sm ${
              isActive ? "bg-primary-container/20 font-bold text-primary" : "text-on-surface-variant hover:bg-surface-container-low"
            }`}
          >
            <Icon name={icon} filled={isActive} size={20} />
            <span className="font-label-sm text-[11px] md:text-label-sm">{label}</span>
          </Link>
        );
      })}
      <span aria-hidden className="mx-xs h-6 w-px shrink-0 bg-outline-variant" />
      <NotificationPopover />
      <ThemeToggle />
    </nav>
  );
}
