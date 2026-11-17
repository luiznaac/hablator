import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// A generated project is served under a sub-path behind the unified dashboard reverse proxy
// (e.g. "/portfolio/"), but runs at "/" in local dev and in the combined Docker image. Override
// with VITE_BASE. See sibling repos' vite.config.ts for the exact same pattern.
//
// `loadEnv(mode, cwd, "")` is what makes `.env` reach this file: Vite does not inject `.env` into
// `process.env`, so reading it directly silently ignored the file.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Dev parity with the image's nginx proxy: the SPA never holds the token, so the dev proxy
  // attaches the same Bearer header from frontend/.env.
  const apiToken = env.AUTH__API_TOKEN;

  return {
    base: env.VITE_BASE ?? (mode === "production" ? "/hablator/" : "/"),
    plugins: [react(), tailwindcss()],
    server: {
      // Strict on purpose: a taken dev port fails loudly instead of auto-incrementing, so the
      // served URL cannot drift from the assigned frontend-dev port or an externally registered
      // origin (e.g. an OAuth redirect).
      port: Number(env.FRONTEND_DEV_PORT ?? 8143),
      strictPort: true,
      proxy: {
        // Dev-only: forward API calls to the backend to dodge CORS.
        "/api": {
          target: env.VITE_API_TARGET ?? "http://localhost:8140",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
          ...(apiToken ? { headers: { Authorization: `Bearer ${apiToken}` } } : {}),
        },
      },
    },
  };
});
