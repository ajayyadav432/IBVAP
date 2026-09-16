/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#090909',
        surface: '#151515',
        elevated: '#1D1D1D',
        accent: {
          DEFAULT: '#FF1118',
          hover: '#E00B12',
          subtle: 'rgba(255, 17, 24, 0.15)',
        },
        border: '#2A2A2A',
        primary: '#FFFFFF',
        secondary: '#A3A3A3',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
