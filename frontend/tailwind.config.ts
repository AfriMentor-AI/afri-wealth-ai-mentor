import type { Config } from "tailwindcss";

// Heritage-Forward Financial Mentor — tokens taken verbatim from the Stitch
// export's DESIGN.md / code.html tailwind.config blocks (light mode is the
// real, provided palette). Dark "Nocturnal Heritage" values were NOT
// actually present in the export (its dark: variants just reuse the light
// tokens) — those are marked clearly in globals.css as our own derivation
// pending real dark tokens from design.
const config: Config = {
  darkMode: ["class", '[data-theme="nocturnal"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        "surface-dim": "var(--surface-dim)",
        "surface-bright": "var(--surface-bright)",
        "surface-container-lowest": "var(--surface-container-lowest)",
        "surface-container-low": "var(--surface-container-low)",
        "surface-container": "var(--surface-container)",
        "surface-container-high": "var(--surface-container-high)",
        "surface-container-highest": "var(--surface-container-highest)",
        "on-surface": "var(--on-surface)",
        "on-surface-variant": "var(--on-surface-variant)",
        "inverse-surface": "var(--inverse-surface)",
        "inverse-on-surface": "var(--inverse-on-surface)",
        outline: "var(--outline)",
        "outline-variant": "var(--outline-variant)",
        "surface-tint": "var(--surface-tint)",
        primary: "var(--primary)",
        "on-primary": "var(--on-primary)",
        "primary-container": "var(--primary-container)",
        "on-primary-container": "var(--on-primary-container)",
        "inverse-primary": "var(--inverse-primary)",
        secondary: "var(--secondary)",
        "on-secondary": "var(--on-secondary)",
        "secondary-container": "var(--secondary-container)",
        "on-secondary-container": "var(--on-secondary-container)",
        tertiary: "var(--tertiary)",
        "on-tertiary": "var(--on-tertiary)",
        "tertiary-container": "var(--tertiary-container)",
        "on-tertiary-container": "var(--on-tertiary-container)",
        error: "var(--error)",
        "on-error": "var(--on-error)",
        "error-container": "var(--error-container)",
        "on-error-container": "var(--on-error-container)",
        "primary-fixed": "var(--primary-fixed)",
        "primary-fixed-dim": "var(--primary-fixed-dim)",
        "on-primary-fixed": "var(--on-primary-fixed)",
        "on-primary-fixed-variant": "var(--on-primary-fixed-variant)",
        "secondary-fixed": "var(--secondary-fixed)",
        "secondary-fixed-dim": "var(--secondary-fixed-dim)",
        "on-secondary-fixed": "var(--on-secondary-fixed)",
        "on-secondary-fixed-variant": "var(--on-secondary-fixed-variant)",
        background: "var(--background)",
        "on-background": "var(--on-background)",
        "surface-variant": "var(--surface-variant)",
      },
      fontFamily: {
        "headline-xl": ["Be Vietnam Pro", "system-ui", "sans-serif"],
        "headline-lg": ["Be Vietnam Pro", "system-ui", "sans-serif"],
        "headline-lg-mobile": ["Be Vietnam Pro", "system-ui", "sans-serif"],
        "title-md": ["Be Vietnam Pro", "system-ui", "sans-serif"],
        "body-lg": ["Inter", "system-ui", "sans-serif"],
        "body-md": ["Inter", "system-ui", "sans-serif"],
        "label-sm": ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        "headline-xl": ["40px", { lineHeight: "48px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-lg": ["32px", { lineHeight: "40px", fontWeight: "700" }],
        "headline-lg-mobile": ["28px", { lineHeight: "34px", fontWeight: "700" }],
        "title-md": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "label-sm": ["13px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "600" }],
      },
      spacing: {
        unit: "4px",
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "48px",
        "margin-mobile": "20px",
        gutter: "16px",
      },
      borderRadius: {
        // Verbatim from DESIGN.md frontmatter `rounded:` block. NOTE: this
        // differs from what G1.1 used (which was reverse-engineered from
        // the export's rendered code.html, not DESIGN.md itself) — see
        // README "Token reconciliation" section for the full explanation.
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
};

export default config;
