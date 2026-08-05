"use client";

import React from "react";

type Variant = "primary" | "cta" | "secondary" | "ghost";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

// Pill-shaped, 44px min height, per DESIGN.md Interactive Elements spec.
// "cta" reproduces the hero button-shadow press effect from the splash screen;
// "primary" is the flatter in-context action button used elsewhere (e.g. persona cards).
const variantClasses: Record<Variant, string> = {
  cta: "bg-primary-container text-on-primary-container button-shadow active:translate-y-1",
  primary: "bg-primary text-on-primary active:scale-95",
  secondary: "bg-surface-container-low text-on-surface border border-outline-variant active:scale-95",
  ghost: "bg-transparent text-on-surface hover:bg-surface-container-low",
};

export function Button({ variant = "primary", className = "", children, ...props }: ButtonProps) {
  return (
    <button
      className={`tap-target inline-flex items-center justify-center gap-sm rounded-full px-lg py-md font-label-sm text-label-sm font-semibold transition-transform disabled:opacity-40 disabled:active:scale-100 ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
