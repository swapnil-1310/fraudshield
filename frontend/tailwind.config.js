/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sebi: {
          blue: "#0A2540",
          accent: "#0066CC",
          dark: "#080F1D",
          card: "#0F172A",
          border: "#1E293B"
        }
      }
    },
  },
  plugins: [],
}
