import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy /api and /auth requests to the backend in development
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
