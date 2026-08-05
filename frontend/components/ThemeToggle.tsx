"use client";

import { Icon } from "./Icon";
import { useAppDispatch, useAppState } from "@/lib/store";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme } = useAppState();
  const dispatch = useAppDispatch();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={theme === "nocturnal"}
      aria-label={theme === "heritage" ? "Switch to Nocturnal Heritage (dark mode)" : "Switch to Heritage-Forward (light mode)"}
      onClick={() => dispatch({ type: "TOGGLE_THEME" })}
      className={`tap-target flex items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low ${className}`}
    >
      <Icon name={theme === "heritage" ? "dark_mode" : "light_mode"} />
    </button>
  );
}
