import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev-server ports follow the same env vars `scripts/e2e-start.mjs` uses, so a second
// checkout (git worktree, parallel E2E run) can bring up its own stack without the browser
// silently proxying /api to the other one's backend.
const apiHost = process.env.STUDIO_API_HOST || "127.0.0.1";
const apiPort = process.env.STUDIO_API_PORT || "8758";
const apiTarget = `http://${apiHost}:${apiPort}`;
const webPort = Number(process.env.PLAYWRIGHT_WEB_PORT || process.env.STUDIO_WEB_PORT || 5173);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: webPort,
    strictPort: true,
    proxy: {
      "/api": apiTarget,
      "/media": apiTarget,
    },
  },
  preview: {
    host: "127.0.0.1",
    port: Number(process.env.PLAYWRIGHT_PREVIEW_PORT || 4173),
    strictPort: true,
    proxy: {
      "/api": apiTarget,
      "/media": apiTarget,
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
