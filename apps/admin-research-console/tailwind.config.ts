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
        primary: "#7e5700",
        "on-primary": "#ffffff",
        "primary-container": "#c8922a",
        "on-primary-container": "#462f00",
        secondary: "#1b6d24",
        "on-secondary": "#ffffff",
        "secondary-container": "#a0f399",
        "on-secondary-container": "#217128",
        tertiary: "#5f5e5e",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#9d9b9b",
        error: "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
        background: "#fcf9f3",
        surface: "#fcf9f3",
        "on-surface": "#1c1c18",
        "surface-variant": "#e5e2dc",
        "on-surface-variant": "#504536",
        outline: "#827564",
        "outline-variant": "#d4c4b0",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f6f3ed",
        "surface-container": "#f0eee8",
        "surface-container-high": "#ebe8e2",
        "surface-container-highest": "#e5e2dc",
        "surface-bright": "#fcf9f3",
        "surface-dim": "#dcdad4",
        "inverse-surface": "#31312d",
        "inverse-on-surface": "#f3f0ea",
        "console-accent": "#2B4C7E",
        "console-bg": "#F1F4F9",
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        full: "9999px",
      },
      spacing: {
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "48px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        headline: ["Be Vietnam Pro", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "label-sm": ["13px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "600" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
        "title-md": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "headline-lg": ["32px", { lineHeight: "40px", fontWeight: "700" }],
        "headline-xl": ["40px", { lineHeight: "48px", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
    },
  },
  plugins: [],
};

export default config;
