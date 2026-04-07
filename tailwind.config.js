/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ix: {
          bg: '#070b14',
          surface: '#0d1b2a',
          surface2: '#0f2035',
          text: '#c8d8e8',
          accent: '#7eb8d4',
          purple: '#9b7fc7',
          gold: '#d4af37',
          green: '#4ade80',
          red: '#e05252',
          dim: '#4a5568'
        }
      },
      borderRadius: {
        ix: '8px',
        modal: '12px'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      }
    }
  },
  plugins: []
}
