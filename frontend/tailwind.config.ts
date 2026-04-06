import type { Config } from "tailwindcss";

const config: Config = {
  // Scan every file that can emit Tailwind classes (routes, features, shared, etc.)
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
