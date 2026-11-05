/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// La interfaz solo habla con la API por HTTP. En desarrollo, Vite reenvía /api al
// backend, así el navegador no necesita CORS (todo sale del mismo origen).
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: backend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
    // Docker Desktop en Windows no avisa los cambios de archivos: se revisan a mano.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
