import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import ProjectEditor from "./pages/ProjectEditor";
import CoDirectorPage from "./pages/CoDirectorPage";
import SourceManagerPage from "./pages/SourceManager";
import ModelRadarWorkspace from "./components/ModelRadarWorkspace";
import Version12DeferredPage from "./components/Version12DeferredPage";
import ProductionSuiteWorkspace from "./components/ProductionSuiteWorkspace";
import VideoRuntimeDiagnostics from "./pages/VideoRuntimeDiagnostics";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import RuntimeManager from "./components/docker-runtime/RuntimeManager";
import { LocalRuntimeSettings } from "./components/Settings/LocalRuntime";
// M2.8 / M2.13 workspace foundations retained for Version 1.2; V1.1 routes show deferral pages.
import { CoDirectorHost, CoDirectorSessionProvider } from "./components/CoDirector";
import { ProductionControlDock } from "./components/production-dock";
import { ErrorBoundary } from "./components/ErrorBoundary";
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
import "./components/CoDirector/codirector-cinematic.css";
import "./components/generationStudio/aurora-landing.css";
import "./theme/aurora-plates.css";

export default function App() {
  return (
    <ErrorBoundary>
      <LanguageProvider>
        <BrowserRouter>
          <CoDirectorSessionProvider>
            <StudioApiOutageBanner />
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/project/:id" element={<ProjectEditor />} />
              <Route path="/co-director" element={<CoDirectorPage />} />
              <Route path="/source-manager" element={<SourceManagerPage />} />
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
              <Route path="/settings/local-runtime" element={<LocalRuntimeSettings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <CoDirectorHost />
            <ProductionControlDock />
          </CoDirectorSessionProvider>
        </BrowserRouter>
      </LanguageProvider>
    </ErrorBoundary>
  );
}
