import { ModelMenuDrawer } from "./ModelMenuDrawer";
import type { ProductionDockApi } from "./useProductionDock";

export function ImageMenu(props: { open: boolean; dock: ProductionDockApi; onClose: () => void }) {
  return <ModelMenuDrawer {...props} title="Image" modality="image" />;
}
