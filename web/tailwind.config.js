/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#0F0D0A',
          900: '#15120D',
          850: '#1C1811',
          800: '#252015',
          700: '#342B1E',
          600: '#4A3E2B',
        },
        parchment: {
          100: '#F4EDDE',
          200: '#E7DCC4',
          300: '#CFC19F',
          400: '#A89A78',
          500: '#857657',
          600: '#655A44',
        },
        marigold: {
          200: '#FFE3B3',
          300: '#FFC86E',
          400: '#FFAC38',
          500: '#F28C13',
          600: '#C96A06',
          700: '#9A5107',
        },
        peacock: {
          200: '#B8F4E8',
          300: '#7DECD8',
          400: '#3AD9BE',
          500: '#14B89F',
          600: '#0C7F6E',
          700: '#0A5F53',
        },
        clay: {
          300: '#F5A48E',
          400: '#E97B5C',
          500: '#D35A38',
          600: '#A84326',
        },
        orchid: {
          200: '#E2D4FF',
          300: '#C9B1FF',
          400: '#AC8DFF',
          500: '#8B66F0',
          600: '#6B46C9',
        },
        rosewood: {
          300: '#F6A8BB',
          400: '#E97E99',
          500: '#CE5578',
          600: '#A63D5C',
        },
        moss: {
          300: '#BFE3B0',
          400: '#93CC7E',
          500: '#6BAE57',
          600: '#4E853D',
        },
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'Noto Serif', 'serif'],
        sans: ['"Hanken Grotesk"', '"Noto Sans"', 'system-ui', 'sans-serif'],
        mono: ['"Spline Sans Mono"', '"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 0 rgba(244, 237, 222, 0.04) inset, 0 18px 40px -22px rgba(0, 0, 0, 0.7)',
        pop: '0 12px 32px -12px rgba(242, 140, 19, 0.45)',
        drawer: '0 24px 60px -20px rgba(0, 0, 0, 0.8)',
      },
      keyframes: {
        rise: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
      animation: {
        rise: 'rise 0.45s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 0.2s ease-out both',
      },
    },
  },
  plugins: [],
}
