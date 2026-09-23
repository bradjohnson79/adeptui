/**
 * Sequential Continue helper: persist handoff, then navigate to the Image
 * Generator (production-still successor of Scene Creator Standard) using the
 * server-resolved destination. Never navigate on persist failure. Never fire
 * persist and navigation concurrently.
 */
import { api } from "../../../api";

export type ProductionHandoffPayload = {
  sceneId: string;
  sheetId: string;
  handoffId: string;
  revision: number;
  selectedProfileId: string | null;
  ersPackageId: string;
  ersLibraryAssetId: string;
  spatialMapId: string;
  name?: string;
  displayName?: string;
  noop?: boolean;
};

export type PersistThenOpenOptions = {
  projectId: string;
  sceneId?: string;
  sheetId?: string;
  spatialMapId?: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
  onClose?: () => void;
};

export async function persistThenOpenSceneCreator(
  options: PersistThenOpenOptions,
): Promise<ProductionHandoffPayload> {
  const projectId = (options.projectId || "").trim();
  if (!projectId) {
    throw new Error("Open a project before continuing to the Image Generator.");
  }
  const payload = await api.sceneCreator.productionHandoff(projectId, {
    scene_id: options.sceneId || "",
    sheet_id: options.sheetId || "",
    spatial_map_id: options.spatialMapId || "",
  });
  const extra: Record<string, string> = {
    scene_id: payload.sceneId,
    sheet_id: payload.sheetId,
    spatialProfileId: payload.handoffId,
    handoffId: payload.handoffId,
  };
  // Scene Creator Standard is retired — the Image Generator owns production
  // still generation (Image Generator v1.1 triad). The ERS handoff payload
  // still persists server-side; creators continue in the Image Generator.
  options.onGoTab?.("imagegen", extra);
  options.onClose?.();
  return payload;
}
