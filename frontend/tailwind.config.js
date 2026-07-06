/** @type {importar('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Preparar el modo oscuro basado en clases
  theme: {
    extend: {
      colors: {
        // Paleta temática de colores obligatoria
        darkBg: '#1A1D20',     // antecedentes primarios
        techBlue: '#0066FF',   // Enviar botones
        glowBlue: '#00D2FF',   // Brillos de neón y enfoque de entrada
        whitePure: '#FFFFFF',  // Texto y bordes
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}