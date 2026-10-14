"use client";
import { useAppDispatch, useAppState } from "@/lib/store";

/** Light / dark / system switch from the Stitch shell. `vertical` is the chat rail variant. */
export function ThemeSwitch({ vertical = false, className = "" }: { vertical?: boolean; className?: string }) {
  const { theme } = useAppState();
  const dispatch = useAppDispatch();
  const items = [
    { key: "light", icon: "light_mode", title: "Light mode" },
    { key: "dark", icon: "dark_mode", title: "Dark mode" },
    { key: "system", icon: vertical ? "settings_brightness" : "desktop_windows", title: "System mode" },
  ] as const;
  function pick(k: (typeof items)[number]["key"]) {
    if (k === "light") dispatch({ type: "SET_THEME", theme: "heritage" });
    else if (k === "dark") dispatch({ type: "SET_THEME", theme: "nocturnal" });
    else {
      const dark = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
      dispatch({ type: "SET_THEME", theme: dark ? "nocturnal" : "heritage" });
    }
  }
  const active = theme === "nocturnal" ? "dark" : "light";
  return (
    <div
      role="group"
      aria-label="Theme"
      className={
        vertical
          ? `flex flex-col items-center gap-1 rounded-full bg-surface-container-high/60 p-1 text-on-surface-variant ${className}`
          : `flex items-center rounded-full border border-outline-subtle bg-surface-default p-1 ${className}`
      }
    >
      {items.map((it) => {
        const on = it.key === active;
        const size = vertical ? "h-7 w-7" : "p-1";
        return (
          <button
            key={it.key}
            type="button"
            title={it.title}
            aria-label={it.title}
            aria-pressed={on}
            onClick={() => pick(it.key)}
            className={`${size} flex items-center justify-center rounded-full transition-colors ${
              on ? "bg-paper text-primary shadow-sm" : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">{it.icon}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Single icon button used where the 3-way switch has no room (mobile headers). */
export function ThemeToggleButton({ className = "" }: { className?: string }) {
  const { theme } = useAppState();
  const dispatch = useAppDispatch();
  const dark = theme === "nocturnal";
  return (
    <button
      type="button"
      aria-label="Toggle theme"
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => dispatch({ type: "TOGGLE_THEME" })}
      className={`flex h-11 w-11 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface ${className}`}
    >
      <span className="material-symbols-outlined text-[22px]">{dark ? "light_mode" : "dark_mode"}</span>
    </button>
  );
}
