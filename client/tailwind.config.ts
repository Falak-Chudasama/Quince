import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Host Grotesk', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Unbounded', 'Host Grotesk', 'system-ui', 'sans-serif'],
        mono: ['Azeret Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        stone: {
          50: '#F8F9F5',
          100: '#F1F3EE',
          200: '#E5E7E1',
          300: '#D4D7CE',
          400: '#A3A89C',
          500: '#6D7366',
          600: '#50554B',
          700: '#393D35',
          800: '#252822',
          850: '#1D1F1B',
          900: '#181915',
          950: '#121310',
        },
        quince: {
          50: '#FFFBEB',
          100: '#FEF3C7',
          200: '#FFE699',
          300: '#FCD34D',
          400: '#F9AF49',
          500: '#E59524',
          600: '#C47714',
          leaf: '#89D66D',
          'leaf-dark': '#5EA844',
        },
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        '3xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.25rem',
        '4xl': '1.5rem',
      },
      boxShadow: {
        '2xs': '0 1px 2px 0 rgba(0,0,0,0.03)',
        soft: '0 4px 20px -2px rgba(0,0,0,0.06), 0 1px 4px -1px rgba(0,0,0,0.03)',
        glass: '0 8px 32px -4px rgba(0,0,0,0.08), 0 2px 8px -2px rgba(0,0,0,0.04)',
        'glow-amber': '0 0 24px -4px rgba(249,175,73,0.32)',
      },
      animation: {
        'float-breathe': 'floatBreathe 6s ease-in-out infinite',
        'pulse-soft': 'pulseSoft 2.4s ease-in-out infinite',
        'slide-up': 'slideUp 180ms cubic-bezier(0.2, 0.8, 0.2, 1)',
      },
      keyframes: {
        floatBreathe: {
          '0%, 100%': { transform: 'translateY(0px) scale(1)' },
          '50%': { transform: 'translateY(-4px) scale(1.015)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.75', transform: 'scale(0.98)' },
          '50%': { opacity: '1', transform: 'scale(1.05)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
