"use client";

import React from "react";

interface ChipProps {
  label: string;
  active?: boolean;
  onClick?: () => void;
}

// DESIGN.md's Components section describes "Quick-Reply Chips" using
// "Learning" or "Community" semantic colors for background — but no hex
// values for those two names exist anywhere in the token set (only
// primary/secondary/tertiary/error families are actually defined). The
// real intake_sector_question screen reference instead shows selected
// chips using primary/primary-container, which is what this matches.
// Flagging rather than inventing hex values for "Learning"/"Community" —
// those need to come from design as real tokens before this chip can
// honor that specific line of the spec.
export function Chip({ label, active = false, onClick }: ChipProps) {
  return (
    <button
      onClick={onClick}
      className={`tap-target rounded-full border px-md py-sm font-body-md text-body-md transition-all active:scale-95 ${
        active
          ? "border-primary bg-primary-container text-on-primary-container"
          : "border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:bg-primary-container hover:text-on-primary-container"
      }`}
      aria-pressed={active}
    >
      {label}
    </button>
  );
}
