import { ModelMenuDrawer } from "./ModelMenuDrawer";
import type { ProductionDockApi } from "./useProductionDock";

export function LlmMenu(props: { open: boolean; dock: ProductionDockApi; onClose: () => void }) {
  return <ModelMenuDrawer {...props} title="LLM" modality="llm" />;
}
