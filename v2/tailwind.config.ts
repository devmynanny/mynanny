import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#121826",
        mist: "#f5f1ea",
        paper: "#ffffff",
        moss: "#4c8c7a",
        gold: "#c89b4a",
        navy: "#1f4e79"
      },
      boxShadow: {
        soft: "0 18px 50px rgba(18,24,38,0.10)"
      },
      borderRadius: {
        "2xl": "1.5rem"
      }
    }
  },
  plugins: []
};

export default config;
