import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/fraunces/500.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import { App } from "./App";
import { ContactPage } from "./components/ContactPage";
import { GuideDock } from "./guide/GuideDock";
import "./styles/tokens.css";
import "./styles/site.css";
import "./styles/guide.css";

const DocsApp = lazy(() => import("./docs/DocsApp").then((mod) => ({ default: mod.DocsApp })));

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root");

const path = window.location.pathname.replace(/\/+$/, "") || "/";
const docs = path === "/docs" || path.startsWith("/docs/");
const contact = path === "/contact";

createRoot(root).render(
  <StrictMode>
    {docs ? (
      <Suspense fallback={<p className="docs-loading">Loading documentation…</p>}>
        <DocsApp />
      </Suspense>
    ) : contact ? (
      <ContactPage />
    ) : (
      <App />
    )}
    <GuideDock />
  </StrictMode>,
);

