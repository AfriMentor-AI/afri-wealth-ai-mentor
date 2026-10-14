"use client";
import { useEffect, useState } from "react";

/** null until mounted (so server + first client render match), then true/false. */
export function useMinWidth(px: number): boolean | null {
  const [match, setMatch] = useState<boolean | null>(null);
  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${px}px)`);
    const update = () => setMatch(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [px]);
  return match;
}
