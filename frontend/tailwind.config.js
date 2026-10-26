/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Trebuchet MS"', '"Lucida Sans Unicode"', '"Lucida Grande"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
