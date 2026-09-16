"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { useAppDispatch } from "@/lib/store";

const tabs = [
  { href: "/chat", label: "Chat", icon: "chat_bubble" },
  { href: "/goals", label: "Goals", icon: "target" },
  { href: "/library", label: "Library", icon: "auto_stories" },
  { href: "/progress", label: "Progress", icon: "query_stats" },
  // Research Console is hidden from the consumer app; dedicated console lives in apps/admin-research-console
];

// A normal flex sibling in the app shell now, not `fixed` — sized by its
// own content (h-16 row on mobile, w-20 column on desktop) rather than an
// overlay that content elsewhere has to guess padding to clear.
export function BottomTabNav() {
  const pathname = usePathname();
  const dispatch = useAppDispatch();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex h-16 w-full items-center justify-around border-t border-outline-variant bg-surface px-sm md:static md:h-full md:w-20 md:flex-col md:justify-start md:gap-2 md:border-b-0 md:border-t-0 md:border-r md:py-lg lg:w-56 lg:items-stretch"
      aria-label="Main"
    >
      <div className="hidden lg:flex lg:flex-col lg:gap-0.5 lg:px-lg lg:pb-lg">
        <p className="font-headline-lg text-2xl font-bold text-primary">AfriMentor</p>
        <p className="font-label-sm text-[10px] uppercase tracking-wider text-on-surface-variant">Dignified Growth</p>
      </div>
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
      <button
        type="button"
        onClick={() => dispatch({ type: "OPEN_NEW_GOAL_MODAL" })}
        className="mt-auto hidden items-center justify-center gap-sm rounded-full bg-primary px-lg py-md font-title-md text-title-md text-on-primary transition-opacity hover:opacity-90 active:scale-95 lg:flex"
      >
        <Icon name="add" size={20} />
        New Goal
      </button>
    </nav>
  );
}
