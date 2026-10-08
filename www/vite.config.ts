import react from "@vitejs/plugin-react";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { loadEnv, type Plugin } from "vite";
import { defineConfig } from "vitest/config";
import { faq, site } from "./src/content";
import { headTags, noscriptSummary, resolveSiteUrl, robotsTxt, sitemapXml } from "./src/seo";
import { handleContact } from "./server/contact";
import { handleGuide } from "./server/guide";

function publishedDocPaths(docsRoot: string): string[] {
  const paths = ["/docs"];
  let categories: string[] = [];
  try {
    categories = readdirSync(docsRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);
  } catch {
    return paths;
  }
  for (const category of categories) {
    const dir = path.join(docsRoot, category);
    let listed = false;
    for (const file of readdirSync(dir)) {
      if (!file.endsWith(".md")) continue;
      const source = readFileSync(path.join(dir, file), "utf8");
      const status = /^status:\s*(\S+)/m.exec(source)?.[1];
      const slug = /^slug:\s*(\S+)/m.exec(source)?.[1];
      const declared = /^category:\s*(\S+)/m.exec(source)?.[1];
      if (status !== "published" || !slug || declared !== category) continue;
      if (!listed) {
        paths.push(`/docs/${category}`);
        listed = true;
      }
      paths.push(`/docs/${category}/${slug}`);
    }
  }
  return paths;
}

function guideApi(): Plugin {
  const attach = (server: { middlewares: { use: (handler: (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse, next: () => void) => void) => void } }) => {
    server.middlewares.use((req, res, next) => {
      const url = req.url?.split("?")[0];
      if (url !== "/api/guide" || req.method !== "POST") {
        next();
        return;
      }
      const origin = req.headers.origin;
      const host = req.headers.host;
      if (origin && host && !origin.endsWith(`://${host}`)) {
        res.statusCode = 403;
        res.end();
        return;
      }
      const pieces: Buffer[] = [];
      let size = 0;
      req.on("data", (piece: Buffer) => {
        size += piece.length;
        if (size > 16_000) {
          res.statusCode = 413;
          res.end();
          req.destroy();
          return;
        }
        pieces.push(piece);
      });
      req.on("end", () => {
        void (async () => {
          let body: { message?: unknown; history?: unknown; page?: unknown } = {};
          try {
            body = JSON.parse(Buffer.concat(pieces).toString("utf8")) as typeof body;
          } catch {
            res.statusCode = 400;
            res.end();
            return;
          }
          const trustProxy = process.env.GUIDE_TRUST_PROXY === "1";
          const forwarded = req.headers["x-forwarded-for"];
          const forwardedKey = trustProxy ? (Array.isArray(forwarded) ? forwarded[0] : forwarded)?.split(",")[0]?.trim() : "";
          const clientKey = forwardedKey || req.socket.remoteAddress || "local";
          const response = await handleGuide(body, { clientKey });
          res.statusCode = response.status;
          response.headers.forEach((value, key) => res.setHeader(key, value));
          if (!response.body) {
            res.end();
            return;
          }
          const reader = response.body.getReader();
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            res.write(value);
          }
          res.end();
        })().catch(() => {
          if (!res.headersSent) res.statusCode = 200;
          res.end(`event: error\ndata: ${JSON.stringify({ message: "The Adept UI Guide is temporarily unavailable. You can still search the documentation." })}\n\n`);
        });
      });
    });
  };
  return {
    name: "adept-guide",
    configureServer(server) {
      attach(server);
    },
    configurePreviewServer(server) {
      attach(server);
    },
  };
}

function contactApi(): Plugin {
  const attach = (server: { middlewares: { use: (handler: (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse, next: () => void) => void) => void } }) => {
    server.middlewares.use((req, res, next) => {
      const url = req.url?.split("?")[0];
      if (url !== "/api/contact" || req.method !== "POST") {
        next();
        return;
      }
      const originHeader = req.headers.origin;
      const host = req.headers.host;
      if (originHeader && host && !originHeader.endsWith(`://${host}`)) {
        res.statusCode = 403;
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ message: "We couldn't send your message right now. Please try again." }));
        return;
      }
      const pieces: Buffer[] = [];
      let size = 0;
      let rejected = false;
      req.on("data", (piece: Buffer) => {
        size += piece.length;
        if (size > 12_000) {
          rejected = true;
          res.statusCode = 413;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ message: "Enter a shorter message." }));
          req.destroy();
        } else {
          pieces.push(piece);
        }
      });
      req.on("end", () => {
        if (rejected) return;
        void (async () => {
          const trustProxy = process.env.CONTACT_TRUST_PROXY === "1";
          const forwarded = req.headers["x-forwarded-for"];
          const forwardedKey = trustProxy ? (Array.isArray(forwarded) ? forwarded[0] : forwarded)?.split(",")[0]?.trim() : "";
          const clientKey = forwardedKey || req.socket.remoteAddress || "local";
          const result = await handleContact(Buffer.concat(pieces).toString("utf8"), { clientKey });
          res.statusCode = result.status;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ message: result.body.message }));
        })().catch(() => {
          if (res.headersSent) return;
          res.statusCode = 502;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ message: "We couldn't send your message right now. Please try again." }));
        });
      });
    });
  };
  return {
    name: "adept-contact",
    configureServer(server) {
      attach(server);
    },
    configurePreviewServer(server) {
      attach(server);
    },
  };
}

function adeptSeo(origin: string | null): Plugin {
  return {
    name: "adept-seo",
    transformIndexHtml(html) {
      const head = headTags({ origin, name: site.name, description: site.description });
      const body = noscriptSummary({
        title: site.title,
        description: site.description,
        faqs: faq.items,
      });
      return html.replace("<!--seo:head-->", head).replace("<!--seo:body-->", body);
    },
    writeBundle(options) {
      const dir = options.dir;
      if (!dir || !origin) return;
      const docsRoot = path.resolve(path.dirname(dir), "docs");
      const pages = ["/", "/contact", ...publishedDocPaths(docsRoot)];
      writeFileSync(path.join(dir, "sitemap.xml"), sitemapXml(origin, pages));
      writeFileSync(path.join(dir, "robots.txt"), robotsTxt(origin));
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  if (env.OPENAI_API_KEY) process.env.OPENAI_API_KEY = env.OPENAI_API_KEY;
  if (env.CHAT_MODEL) process.env.CHAT_MODEL = env.CHAT_MODEL;
  for (const key of ["CONTACT_TO", "CONTACT_FROM", "CONTACT_PROVIDER", "CONTACT_WEBHOOK_URL", "RESEND_API_KEY", "CONTACT_TRUST_PROXY"]) {
    if (env[key]) process.env[key] = env[key];
  }
  const origin = resolveSiteUrl(env.VITE_SITE_URL || process.env.VITE_SITE_URL);
  return {
    plugins: [react(), adeptSeo(origin), guideApi(), contactApi()],
    server: { host: "127.0.0.1", port: 5193, strictPort: true },
    preview: { host: "127.0.0.1", port: 5193, strictPort: true },
    build: {
      outDir: "dist",
      assetsInlineLimit: 4096,
      target: "es2022",
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.ts", "server/**/*.test.ts"],
    },
  };
});
