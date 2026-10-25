import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The browser only talks to this dev server. `/api` is forwarded to the Django gateway, so
// the gateway needs no CORS setup. Set GATEWAY_URL if Django is not on port 8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const gateway = env.GATEWAY_URL || "http://localhost:8000";
  // "^/api/" and not "/api": a plain prefix would also catch the app's own /api-keys page.
  const proxy = { "^/api/": { target: gateway, changeOrigin: true } };
  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 5173, proxy },
  };
});
