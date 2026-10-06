import { AppChrome } from "../components/dashboard/AppChrome";
import { ComfyManager } from "../components/comfy-manager/ComfyManager";

export default function ComfyManagerPage() {
  return (
    <>
      <AppChrome variant="home" />
      <main>
        <ComfyManager />
      </main>
    </>
  );
}
