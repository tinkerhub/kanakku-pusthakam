import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#FBB905",
        ink: "#E5E7EB",
        bg: "#09090B",
        surface: "#111827",
        panel: "#18181B",
        muted: "#9CA3AF",
        line: "#27272A",
        success: "#22C55E",
        danger: "#F87171",
        warn: "#F59E0B",
      },
    },
  },
  plugins: [],
} satisfies Config;
