/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.ts"],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"Share Tech Mono"', '"JetBrains Mono"', "monospace"],
        display: ['"JetBrains Mono"', "monospace"],
      },
      colors: {
        crt: {
          950: "#060a08", 900: "#0a0f0d", 850: "#0f1714", 800: "#14201b", 700: "#1b2d26",
          green: "#00ff88", amber: "#ffaa00", cyan: "#00e5ff", crimson: "#ff3344", dim: "#234135",
        },
      },
    },
  },
  plugins: [],
};
