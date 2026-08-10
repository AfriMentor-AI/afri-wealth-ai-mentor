"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { useAppDispatch, useAppState } from "@/lib/store";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme } = useAppState();
  const dispatch = useAppDispatch();
  // Belt-and-suspenders on top of the store.tsx fix: don't render the
  // theme-dependent icon at all until after mount. This is the standard
  // pattern (same one next-themes uses) — it guarantees this component
  // can never be a hydration-mismatch source, regardless of any timing
  // subtlety elsewhere, by rendering something static-and-identical on
  // both server and client for the first render, full stop.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={mounted && theme === "nocturnal"}
      aria-label={theme === "heritage" ? "Switch to Nocturnal Heritage (dark mode)" : "Switch to Heritage-Forward (light mode)"}
      onClick={() => dispatch({ type: "TOGGLE_THEME" })}
      className={`tap-target flex items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low ${className}`}
    >
      {mounted ? <Icon name={theme === "heritage" ? "dark_mode" : "light_mode"} /> : <span className="h-6 w-6" aria-hidden />}
    </button>
  );
}
