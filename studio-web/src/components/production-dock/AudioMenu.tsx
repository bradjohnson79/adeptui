import { ModelMenuDrawer } from "./ModelMenuDrawer";
import type { ProductionDockApi } from "./useProductionDock";

export function AudioMenu(props: { open: boolean; dock: ProductionDockApi; onClose: () => void }) {
  return <ModelMenuDrawer {...props} title="Audio" modality="audio" />;
}
