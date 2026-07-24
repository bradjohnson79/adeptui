import { Link, useSearchParams } from "react-router-dom";
import { CoDirectorFullScreen } from "../components/CoDirector";

export default function CoDirectorPage() {
  const [params] = useSearchParams();
  const projectId = params.get("projectId");

  return (
    <>
      <div className="codirector-fullscreen-chrome">
        <Link to={projectId ? `/project/${projectId}` : "/"} className="button-link">
          ← Back to {projectId ? "project" : "home"}
        </Link>
      </div>
      <CoDirectorFullScreen />
    </>
  );
}
