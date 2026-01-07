/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Colores del sistema SIDEFA
        sidefa: {
          blue: '#4A90A4',
          yellow: '#FFD700',
          orange: '#FF8C00',
          green: '#28A745',
          red: '#DC3545',
        }
      },
      fontFamily: {
        // Fuente similar a SIDEFA
        sans: ['Tahoma', 'Arial', 'sans-serif'],
      }
    },
  },
  plugins: [],
}