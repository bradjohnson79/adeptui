/**
 * Informational Version 1.2 roadmap page for deferred native-3D surfaces.
 * Not an error state — guides users to the supported Version 1.1 workflow.
 */
import { Link } from "react-router-dom";
import { StudioChrome } from "./dashboard/StudioChrome";

type Props = {
  title: string;
  testId: string;
};

export default function Version12DeferredPage({ title, testId }: Props) {
  return (
    <div className="page v11-deferred-page" data-testid={testId}>
      <StudioChrome
        variant="home"
        breadcrumbs={[{ label: "Home" }, { label: "Coming in Version 1.2" }]}
      />
      <main className="v11-deferred-main" style={{ maxWidth: 720, margin: "2rem auto", padding: "0 1.25rem" }}>
        <p className="eyebrow" data-testid="v11-deferred-label" style={{ opacity: 0.75, marginBottom: "0.5rem" }}>
          Coming in Version 1.2
        </p>
        <h1 style={{ marginTop: 0 }}>{title}</h1>
        <p data-testid="v11-deferred-message">
          Native 3D importing and animation are planned for Adept UI Version 1.2. Version 1.1 uses
          360 panoramic environments and Spatial Map production.
        </p>
        <p data-testid="v11-deferred-guidance">
          For this Version 1.1 production, create a 360 Environment, open the Spatial Map, then set
          camera and lighting direction before generating the scene.
        </p>
        <ul style={{ lineHeight: 1.7 }}>
          <li>
            <Link to="/" data-testid="v11-deferred-home">
              Open Home / projects
            </Link>
          </li>
          <li>Create or upload a 360 Environment (panorama / image collage)</li>
          <li>Open Spatial Map for character and camera blocking</li>
          <li>Set camera and lighting direction, then generate</li>
        </ul>
      </main>
    </div>
  );
}
