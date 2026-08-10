import { ModelMenuDrawer } from "./ModelMenuDrawer";
import type { ProductionDockApi } from "./useProductionDock";

export function VideoMenu(props: { open: boolean; dock: ProductionDockApi; onClose: () => void }) {
  return <ModelMenuDrawer {...props} title="Video" modality="video" />;
}
