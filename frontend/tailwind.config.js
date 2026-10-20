/** @type {import('tailwindcss').Config} */
// TravelMind brand palette (see :root in src/index.css). Class names kept from v1:
// navy = --tm-primary, navy-deep = --tm-text, teal = --tm-secondary, teal-dark = --tm-secondary-hover.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#123B5D', deep: '#172B3A' },
        teal: { DEFAULT: '#0D9488', bright: '#14B8A6', dark: '#0F766E' },
        sky: { DEFAULT: '#DDF5F2' },
        offwhite: '#F5F8FA',
        slate: { text: '#64748B' },
        line: '#D9E2EA',
        success: '#16A34A',
        accent: '#F5B942',
      },
      borderRadius: { tm: '12px' },
      fontFamily: {
        sans: ['Inter', 'Arial', 'sans-serif'],
        display: ['Manrope', 'Inter', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(23,43,58,0.04), 0 4px 16px rgba(23,43,58,0.05)',
        lift: '0 2px 4px rgba(23,43,58,0.06), 0 12px 28px rgba(23,43,58,0.10)',
      },
    },
  },
  plugins: [],
}
