import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        "accent-bright": "rgb(var(--color-accent-bright) / <alpha-value>)",
        "on-accent": "rgb(var(--color-on-accent) / <alpha-value>)",
        secondary: "rgb(var(--color-secondary) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        panel: "rgb(var(--color-panel) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        outline: "rgb(var(--color-outline) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        warn: "rgb(var(--color-warn) / <alpha-value>)",
        info: "rgb(var(--color-info) / <alpha-value>)",
      },
      fontFamily: {
        // Headings — Clash Display (self-hosted). `display` is the explicit utility;
        // h1–h6 default to it via the base layer in index.css.
        display: ['"Clash Display"', "ui-sans-serif", "system-ui", "sans-serif"],
        // Body — Instrument Sans (also the default body font, set in index.css).
        sans: ['"Instrument Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        // Technical labels — JetBrains Mono (IDs, serials, status chips, quantities).
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        brutal: "4px 4px 0 0 rgb(var(--shadow-color))",
        "brutal-sm": "2px 2px 0 0 rgb(var(--shadow-color))",
        "brutal-lg": "6px 6px 0 0 rgb(var(--shadow-color))",
        "hardsoft-blue": "4px 4px 0 0 rgb(var(--shadow-color)), 0 0 12px 0 rgba(125,211,252,0.55)",
        "hardsoft-yellow": "4px 4px 0 0 rgb(var(--shadow-color)), 0 0 12px 0 rgba(252,223,70,0.55)",
        "hardsoft-mint": "4px 4px 0 0 rgb(var(--shadow-color)), 0 0 12px 0 rgba(116,221,156,0.55)",
        "hardsoft-coral": "4px 4px 0 0 rgb(var(--shadow-color)), 0 0 12px 0 rgba(255,138,128,0.55)",
        "hardsoft-pink": "4px 4px 0 0 rgb(var(--shadow-color)), 0 0 12px 0 rgba(249,168,212,0.55)",
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },
      backgroundSize: {
        blueprint: "32px 32px",
      },
    },
  },
  plugins: [],
} satisfies Config;
