import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies /api and /uploads to the FastAPI backend (no CORS needed locally).
// Everything else falls through to the SPA, so routes like /weather, /soil work on refresh.
const API_TARGET = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": API_TARGET,
      "/uploads": API_TARGET,
    },
  },
});
