import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function removeApiPrefix(path: string): string {
  return path.replace(/^\/api/, "");
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: removeApiPrefix,
      },
    },
  },
});
