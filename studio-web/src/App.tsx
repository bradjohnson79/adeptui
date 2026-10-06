import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Home from "./pages/Home";

const ProjectEditor = lazy(() => import("./pages/ProjectEditor"));
const CoDirectorPage = lazy(() => import("./pages/CoDirectorPage"));
const SourceManagerPage = lazy(() => import("./pages/SourceManager"));
const ModelRadarWorkspace = lazy(() => import("./components/ModelRadarWorkspace"));
const Version12DeferredPage = lazy(() => import("./components/Version12DeferredPage"));
const ProductionSuiteWorkspace = lazy(() => import("./components/ProductionSuiteWorkspace"));
const VideoRuntimeDiagnostics = lazy(() => import("./pages/VideoRuntimeDiagnostics"));
const DiagnosticsPage = lazy(() => import("./pages/DiagnosticsPage").then((mod) => ({ default: mod.DiagnosticsPage })));
const RuntimeManager = lazy(() => import("./components/docker-runtime/RuntimeManager"));
const LocalRuntimeSettings = lazy(() =>
  import("./components/Settings/LocalRuntime").then((mod) => ({ default: mod.LocalRuntimeSettings })),
);
const ComfyManagerPage = lazy(() => import("./pages/ComfyManagerPage"));

function RouteFallback() {
  return (
    <div className="ds-empty-state ds-inline-notice ds-inline-notice--loading route-fallback" role="status">
      Loading…
    </div>
  );
}
// M2.8 / M2.13 workspace foundations retained for Version 1.2; V1.1 routes show deferral pages.
import { CoDirectorHost, CoDirectorSessionProvider } from "./components/CoDirector";
import { ProductionControlDock } from "./components/production-dock";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { StartupSystemsGauge } from "./components/StartupSystemsGauge";
import { StudioApiOutageBanner } from "./components/StudioApiOutageBanner";
import { LanguageProvider } from "./i18n";
import * as studioApiConnection from "./runtime/studioApiConnection";

studioApiConnection.ensureStudioApiConnectionMonitor();
if (typeof window !== "undefined") {
  (window as unknown as { __ADEPT_STUDIO_API__?: typeof studioApiConnection }).__ADEPT_STUDIO_API__ =
    studioApiConnection;
}
import "./theme/tokens.css";
import "./theme/typography.css";
import "./styles.css";
import "./theme/aurora-theme.css";
import "./components/ui/button.css";
import "./components/ui/status.css";
import "./components/ui/table.css";
import "./components/ui/empty-state.css";
import "./components/ui/section-header.css";
import "./components/ui/menu.css";
import "./components/ui/dialog.css";
import "./components/ui/split-pane.css";
import "./components/ui/workspace-card.css";
import "./styles/shared-controls.css";
import "./styles/audio-provider.css";
import "./components/CoDirector/codirector-cinematic.css";
import "./components/generationStudio/aurora-landing.css";
import "./theme/aurora-plates.css";

function SourceManagerRoute() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const projectId = params.get("projectId");
  if (!projectId) return <SourceManagerPage />;
  const next = new URLSearchParams();
  next.set("workspace", "setup");
  next.set("setupSection", "sources");
  next.set("setupMode", params.get("setupMode") || "ai_guided");
  const componentId = params.get("componentId");
  if (componentId) next.set("setupComponent", componentId);
  return <Navigate to={`/project/${encodeURIComponent(projectId)}?${next.toString()}${location.hash || ""}`} replace />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <LanguageProvider>
        <BrowserRouter>
          <CoDirectorSessionProvider>
            <StudioApiOutageBanner />
            <StartupSystemsGauge />
            <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/project/:id" element={<ProjectEditor />} />
              <Route path="/co-director" element={<CoDirectorPage />} />
              <Route path="/source-manager" element={<SourceManagerRoute />} />
              <Route path="/model-radar" element={<ModelRadarWorkspace />} />
              <Route
                path="/virtual-stage"
                element={
                  <Version12DeferredPage title="Virtual Stage" testId="virtual-stage-deferred" />
                }
              />
              <Route
                path="/environment-studio"
                element={
                  <Version12DeferredPage
                    title="3D & Virtual Environment Studio"
                    testId="environment-studio-deferred"
                  />
                }
              />
              <Route path="/production-suite" element={<ProductionSuiteWorkspace />} />
              <Route path="/diagnostics/video-runtime" element={<VideoRuntimeDiagnostics />} />
              <Route path="/diagnostics" element={<DiagnosticsPage />} />
              <Route path="/runtime-manager" element={<RuntimeManager />} />
              <Route path="/setup/comfy" element={<ComfyManagerPage />} />
              <Route path="/settings/local-runtime" element={<LocalRuntimeSettings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Suspense>
            <CoDirectorHost />
            <ProductionControlDock />
          </CoDirectorSessionProvider>
        </BrowserRouter>
      </LanguageProvider>
    </ErrorBoundary>
  );
}
