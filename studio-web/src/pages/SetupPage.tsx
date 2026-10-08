import { useNavigate } from "react-router-dom";
import { SetupWizardPanel } from "../components/SetupWizard";
import { StudioChrome } from "../components/dashboard/StudioChrome";

/**
 * No-project setup. Same SetupWizardPanel and the same app providers as every other route.
 * Opening this page does not create a project and does not write the first-run flag.
 */
export default function SetupPage() {
  const navigate = useNavigate();
  return (
    <div className="app-shell atmosphere" data-testid="setup-wizard-route">
      <StudioChrome
        variant="home"
        onSetup={() => navigate("/setup")}
        breadcrumbs={[{ label: "Home", onClick: () => navigate("/") }, { label: "Setup" }]}
      />
      <main className="studio-page">
        <SetupWizardPanel />
      </main>
    </div>
  );
}
