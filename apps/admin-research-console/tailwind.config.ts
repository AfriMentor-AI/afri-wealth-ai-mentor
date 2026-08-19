import type { Config } from "tailwindcss";

// A dark, developer-tool palette for the internal admin console — distinct
// from frontend/tailwind.config.ts's consumer-facing "Heritage-Forward"
// theme, but reusing its green brand accent (see stitch_afrimentor_ai_design_system's
// rag_corpus_admin_dark / research_console_dashboard mockups, which are dark-only).
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        "surface-inset": "var(--surface-inset)",
        border: "var(--border)",
        "on-surface": "var(--on-surface)",
        "on-surface-dim": "var(--on-surface-dim)",
        accent: "var(--accent)",
        "on-accent": "var(--on-accent)",
        warn: "var(--warn)",
        danger: "var(--danger)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
