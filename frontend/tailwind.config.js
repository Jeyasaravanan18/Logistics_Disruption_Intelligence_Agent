/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        saas: {
          bg: "#f8fafc", // slate-50
          panel: "#ffffff", // white
          border: "#e2e8f0", // slate-200
          text: "#0f172a", // slate-900
          muted: "#64748b", // slate-500
          hover: "#f1f5f9", // slate-100
          primary: "#2563eb", // blue-600
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
