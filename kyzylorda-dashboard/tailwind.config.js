/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "electric-blue": "#3b82f6",
        "warning-orange": "#f97316"
      },
      boxShadow: {
        "glass-lg":
          "0 10px 40px rgba(15,23,42,0.65), 0 0 0 1px rgba(148,163,184,0.15)"
      },
      backdropBlur: {
        xs: "2px"
      }
    }
  },
  plugins: []
};

