import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { startRuntimeBootstrap } from "./runtime/bootstrap.ts";

// Dev-server ports follow the same env vars `scripts/e2e-start.mjs` uses, so a second
// checkout (git worktree, parallel E2E run) can bring up its own stack without the browser
// silently proxying /api to the other one's backend.
const apiHost = process.env.STUDIO_API_HOST || "127.0.0.1";
const apiPort = process.env.STUDIO_API_PORT || "8758";
const apiTarget = `http://${apiHost}:${apiPort}`;
const webPort = Number(process.env.PLAYWRIGHT_WEB_PORT || process.env.STUDIO_WEB_PORT || 5173);

/**
 * Adept Runtime Bootstrap plugin (localhost now; Electron main calls the same
 * `startRuntimeBootstrap` contract later). On dev-server start it automatically
 * brings the canonical Background Services manager online if it is down, and
 * reuses an already-running one (Comfy leave-alone). The browser never launches
 * services one by one — it just polls /api/runtime-manager/status.
 */
function adeptRuntimeBootstrapPlugin(): Plugin {
  return {
    name: "adept-runtime-bootstrap",
    apply: "serve", // dev server only — never run during vitest or production build
    configureServer(server) {
      // Don't block Vite startup; the frontend modal polls readiness while it runs.
      void startRuntimeBootstrap({
        repoRoot: process.env.ADEPT_REPO_ROOT,
        onEvent: (e) => {
          if (e.type === "reused") server.config.logger.info("[adept-runtime] reusing Background Services manager");
          else if (e.type === "starting") server.config.logger.info(`[adept-runtime] starting supervisor pid=${e.supervisorPid}`);
          else if (e.type === "online") server.config.logger.info("[adept-runtime] manager online");
          else if (e.type === "failed") server.config.logger.warn(`[adept-runtime] ${e.reason}`);
        },
      }).catch((err) => server.config.logger.warn(`[adept-runtime] bootstrap error: ${err}`));
    },
  };
}

export default defineConfig({
  plugins: [react(), adeptRuntimeBootstrapPlugin()],
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
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
