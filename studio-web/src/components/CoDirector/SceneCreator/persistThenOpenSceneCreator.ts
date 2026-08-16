/**
 * Sequential Continue helper: persist handoff, then navigate to Standard
 * Scene Creator using the server-resolved destination. Never navigate on
 * persist failure. Never fire persist and navigation concurrently.
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
    throw new Error("Open a project before continuing to Scene Creator.");
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
  options.onGoTab?.("scenecreator", extra);
  options.onClose?.();
  return payload;
}
