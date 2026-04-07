import { resolve } from "path";
import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        dashboard: resolve(__dirname, "dashboard.html"),
        chat: resolve(__dirname, "chat.html"),
        watchlist: resolve(__dirname, "watchlist.html"),
        login: resolve(__dirname, "login.html"),
        register: resolve(__dirname, "register.html"),
      },
    },
  },
});
