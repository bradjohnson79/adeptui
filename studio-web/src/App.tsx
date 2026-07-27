import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import ProjectEditor from "./pages/ProjectEditor";
import CoDirectorPage from "./pages/CoDirectorPage";
import SourceManagerPage from "./pages/SourceManager";
import ModelRadarWorkspace from "./components/ModelRadarWorkspace";
import VirtualStageWorkspace from "./components/VirtualStageWorkspace";
import EnvironmentStudioWorkspace from "./components/EnvironmentStudioWorkspace";
import ProductionSuiteWorkspace from "./components/ProductionSuiteWorkspace";
import { CoDirectorHost, CoDirectorSessionProvider } from "./components/CoDirector";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./styles.css";

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <CoDirectorSessionProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/project/:id" element={<ProjectEditor />} />
            <Route path="/co-director" element={<CoDirectorPage />} />
            <Route path="/source-manager" element={<SourceManagerPage />} />
            <Route path="/model-radar" element={<ModelRadarWorkspace />} />
            <Route path="/virtual-stage" element={<VirtualStageWorkspace />} />
            <Route path="/environment-studio" element={<EnvironmentStudioWorkspace />} />
            <Route path="/production-suite" element={<ProductionSuiteWorkspace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <CoDirectorHost />
        </CoDirectorSessionProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
