/** Vite companion for `npm run api` (:8742 --reload). Product/cert Vite defaults to :8758. */
import { spawn } from "node:child_process";

process.env.STUDIO_API_PORT = process.env.STUDIO_API_PORT || "8742";
const child = spawn("npm", ["--prefix", "studio-web", "run", "dev"], {
  stdio: "inherit",
  shell: true,
  env: process.env,
});
child.on("exit", (code) => process.exit(code ?? 0));
