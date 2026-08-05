"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";

const tabs = [
  { href: "/chat", label: "Chat", icon: "chat_bubble" },
  { href: "/goals", label: "Goals", icon: "target" },
  { href: "/library", label: "Library", icon: "auto_stories" },
  { href: "/progress", label: "Progress", icon: "query_stats" },
];

// A normal flex sibling in the app shell now, not `fixed` — sized by its
// own content (h-16 row on mobile, w-20 column on desktop) rather than an
// overlay that content elsewhere has to guess padding to clear.
export function BottomTabNav() {
  const pathname = usePathname();

  return (
    <nav
      className="flex h-16 shrink-0 items-center justify-around border-t border-outline-variant bg-surface px-sm md:h-auto md:w-20 md:flex-col md:justify-start md:gap-2 md:border-b-0 md:border-t-0 md:border-r md:py-lg lg:w-56 lg:items-stretch"
      aria-label="Main"
    >
      {tabs.map(({ href, label, icon }) => {
        const isActive = pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={`tap-target relative flex flex-1 flex-col items-center justify-center gap-0.5 rounded transition-colors duration-150 active:scale-90 md:flex-none md:flex-row md:justify-center md:gap-2 md:px-md md:py-sm lg:justify-start lg:px-lg ${
              isActive ? "font-bold text-primary md:bg-primary-container/20" : "text-on-surface-variant hover:bg-surface-container-low"
            }`}
          >
            <Icon name={icon} filled={isActive} />
            <span className="font-label-sm text-label-sm">{label}</span>
            {isActive && (
              <span aria-hidden className="absolute -bottom-0.5 h-1 w-1 rounded-full bg-primary md:hidden" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
