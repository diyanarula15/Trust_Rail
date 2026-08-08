import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // `rgb(var(--x) / <alpha-value>)` so both `bg-card` and `bg-card/50`
      // work. A bare `var(--x)` holding a hex breaks every opacity modifier.
      colors: {
        ink: "rgb(var(--ink) / <alpha-value>)",
        paper: "rgb(var(--paper) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        hairline: "rgb(var(--hairline) / <alpha-value>)",
        verified: "rgb(var(--verified) / <alpha-value>)",
        notice: "rgb(var(--notice) / <alpha-value>)",
        fake: "rgb(var(--fake) / <alpha-value>)",
        info: "rgb(var(--info) / <alpha-value>)",
        seal: "rgb(var(--seal) / <alpha-value>)",
      },
      fontFamily: {
        display: ["var(--font-archivo)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      // Softer than the original 6px. The reference site's rounding is one of
      // the clearest reasons it reads as a finished product rather than an
      // internal tool; `rounded` is used almost everywhere already, so
      // changing the default lifts every page at once.
      borderRadius: {
        DEFAULT: "10px",
        lg: "14px",
        xl: "20px",
      },
      maxWidth: {
        prose: "68ch",
      },
    },
  },
  plugins: [],
};

export default config;
