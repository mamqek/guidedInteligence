import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const frontendPort = Number(process.env.GI_FRONTEND_PORT || 5173);
const backendUrl = process.env.GI_BACKEND_URL || "http://127.0.0.1:8790";

export default defineConfig({
  root: "ui",
  plugins: [react()],
  server: {
    port: frontendPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
