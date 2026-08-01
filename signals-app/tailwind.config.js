/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Brand palette — matches aicompareapi.com website.
        bg: '#0b1220',
        surface: '#111a2b',
        card: '#0f1826',
        border: '#1f2937',
        text: '#e5e7eb',
        muted: '#9ca3af',
        // Semantic ONLY — never used for UI chrome (per design spec).
        bull: '#10b981',
        bear: '#ef4444',
        accent: '#3b82f6',
      },
      fontFamily: {
        // Geometric sans for headers, monospace for prices/tickers.
        sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '8px',
      },
    },
  },
  plugins: [],
};
