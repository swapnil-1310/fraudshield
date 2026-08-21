/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        fintech: {
          bg: "#F7FAF8",
          surface: "#FFFFFF",
          green: "#087443",
          action: "#16A05D",
          dark: "#064D32",
          soft: "#EAF7F0",
          verysoft: "#F1F9F5",
          text: "#17211C",
          secondary: "#66736C",
          border: "#E2E9E5",
          red: "#D92D20",
          amber: "#D97706",
          blue: "#2563EB"
        }
      },
      animation: {
        'scanline': 'scanline 2s linear infinite',
        'fade-in-up': 'fadeInUp 0.5s ease-out forwards',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        scanline: {
          '0%': { transform: 'translateY(0)', opacity: '0' },
          '10%': { opacity: '1' },
          '90%': { opacity: '1' },
          '100%': { transform: 'translateY(500px)', opacity: '0' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
