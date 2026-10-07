/**
 * Spatial Map API client — thin typed wrapper over the existing
 * `api.spatialMap` client in `studio-web/src/api.ts`.
 *
 * Reuses the shared client (Law #17). The V1 Cartesian grid fields and camera
 * blocking fields are now accepted by the backend; the small casts below are
 * only because the frozen M411 contract types in `api.ts` predate those fields.
 */
import { api } from "../../../api";
import {
  validatePropAttachment,
  type SpatialMapCreateBody,
  type SpatialMapSceneIntentCreateBody,
  type SpatialMapUpdateBody,
  type SpatialMapDocument,
  type SpatialCharacterPlacementBody,
  type SpatialCharacterPlacementUpdateBody,
  type SpatialPropPlacementBody,
  type SpatialPropPlacementUpdateBody,
  type SpatialPropAttachmentFields,
  type SpinCameraPlacement,
  type SpinPackageManifest,
  type SpinViewKey,
} from "./types";

type CameraBody = {
  label?: string;
  x?: number;
  y?: number;
  z?: number;
  yawDegrees?: number;
  pitchDegrees?: number;
  rollDegrees?: number;
  lensMm?: number;
  heightMeters?: number;
  shotType?: string;
  targetCharacterIds?: string[];
  hero?: boolean;
  lockedFor360?: boolean;
  cameraSlot?: number;
  orientation?: string;
  fovPreset?: string;
  /** Scene Creator Mini: framing-only shot size (auto|wide|medium_wide|medium|medium_close|close_up|extreme_close). */
  shotSize?: string;
  /** Scene Creator Mini: auto|environment|<characterId>. */
  primarySubject?: string;
  attachMode?: "pov" | "free" | "follow";
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridRow?: number;
  gridColumn?: number;
  /** Optional. Default true. false hides the marker only; assignment and coords stay. */
  visible?: boolean;
  /** Active movement to autosave this pose into (avoids M1/M2 switch races). */
  movementSegmentId?: string;
};

export const spatialMapApi = {
  async getMostRecentMap(projectId: string): Promise<SpatialMapDocument | null> {
    const res = await api.spatialMap.listMaps(projectId);
    const docs = (res.documents || []) as unknown as SpatialMapDocument[];
    if (!docs.length) return null;
    const sorted = [...docs].sort((a, b) => {
      const ta = (a.updatedAt || a.createdAt || "").localeCompare(b.updatedAt || b.createdAt || "");
      return -ta;
    });
    return sorted[0] || docs[0];
  },

  async classifyAtlasSource(
    projectId: string,
    assetId: string,
    intendedRoute = "assign",
  ): Promise<{
    kind: string;
    action: string;
    confidence: number;
    message: string;
    pixelsRead: boolean;
    width: number;
    height: number;
  }> {
    return api.spatialMap.classifyAtlasSource(projectId, { assetId, intendedRoute });
  },

  async listMaps(projectId: string): Promise<SpatialMapDocument[]> {
    const res = await api.spatialMap.listMaps(projectId);
    return (res.documents || []) as unknown as SpatialMapDocument[];
  },

  async createMap(projectId: string, body: SpatialMapSceneIntentCreateBody): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.createMap(projectId, body as SpatialMapCreateBody);
    return res.document as unknown as SpatialMapDocument;
  },

  async getMap(projectId: string, documentId: string): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.getMap(projectId, documentId);
    return res.document as unknown as SpatialMapDocument;
  },

  async updateMap(projectId: string, documentId: string, body: SpatialMapUpdateBody): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.updateMap(projectId, documentId, body);
    return res.document as unknown as SpatialMapDocument;
  },

  /** Explicit Save commit (Spatial Map Save Gate). Stamps savedAt + savedVersion. */
  async saveMap(projectId: string, documentId: string): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.saveMap(projectId, documentId);
    return res.document as unknown as SpatialMapDocument;
  },

  async getCorrectAreaState(projectId: string, documentId: string) {
    return api.spatialMap.getCorrectAreaState(projectId, documentId);
  },

  async getCorrectAreaEngine(projectId: string) {
    return api.spatialMap.getCorrectAreaEngine(projectId);
  },

  async startCorrectArea(
    projectId: string,
    documentId: string,
    body: {
      prompt: string;
      maskAssetId: string;
      sourceAssetId?: string;
      width?: number;
      height?: number;
      preserveStyle?: boolean;
      preservePerspective?: boolean;
      preserveLighting?: boolean;
    },
  ) {
    return api.spatialMap.startCorrectArea(projectId, documentId, body);
  },

  async acceptCorrectArea(
    projectId: string,
    documentId: string,
    body?: {
      sessionId?: string;
      outputAssetId?: string;
      resultAssetId?: string;
      acceptToken?: string;
    },
  ) {
    return api.spatialMap.acceptCorrectArea(projectId, documentId, body);
  },

  async undoCorrectArea(projectId: string, documentId: string) {
    return api.spatialMap.undoCorrectArea(projectId, documentId);
  },

  async placeCharacter(
    projectId: string,
    documentId: string,
    body: SpatialCharacterPlacementBody,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.placeCharacter(
      projectId,
      documentId,
      body as Parameters<typeof api.spatialMap.placeCharacter>[2],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async placeProp(
    projectId: string,
    documentId: string,
    body: SpatialPropPlacementBody,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.placeProp(
      projectId,
      documentId,
      body as Parameters<typeof api.spatialMap.placeProp>[2],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async updateCharacter(
    projectId: string,
    documentId: string,
    placementId: string,
    body: SpatialCharacterPlacementUpdateBody,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.moveCharacter(
      projectId,
      documentId,
      placementId,
      body as Parameters<typeof api.spatialMap.moveCharacter>[3],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async updateProp(
    projectId: string,
    documentId: string,
    placementId: string,
    body: SpatialPropPlacementUpdateBody,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.moveProp(
      projectId,
      documentId,
      placementId,
      body as Parameters<typeof api.spatialMap.moveProp>[3],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async removeCharacter(projectId: string, documentId: string, placementId: string): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.removeCharacter(projectId, documentId, placementId);
    return res.document as unknown as SpatialMapDocument;
  },

  async removeProp(projectId: string, documentId: string, placementId: string): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.removeProp(projectId, documentId, placementId);
    return res.document as unknown as SpatialMapDocument;
  },

  async createCamera(projectId: string, documentId: string, body: CameraBody): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.createCamera(
      projectId,
      documentId,
      body as Parameters<typeof api.spatialMap.createCamera>[2],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async updateCamera(projectId: string, documentId: string, cameraId: string, body: CameraBody): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.updateCamera(
      projectId,
      documentId,
      cameraId,
      body as Parameters<typeof api.spatialMap.updateCamera>[3],
    );
    return res.document as unknown as SpatialMapDocument;
  },

  async removeCamera(projectId: string, documentId: string, cameraId: string): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.removeCamera(projectId, documentId, cameraId);
    return res.document as unknown as SpatialMapDocument;
  },

  async attachProp(
    projectId: string,
    documentId: string,
    placementId: string,
    fields: SpatialPropAttachmentFields,
  ): Promise<SpatialMapDocument> {
    const body = validatePropAttachment({
      placementMode: "attached",
      attachedCharacterSlot: fields.attachedCharacterSlot,
      attachedCharacterId: fields.attachedCharacterId,
      relationship: fields.relationship,
      attachmentPoint: fields.attachmentPoint,
    });
    const res = await api.spatialMap.attachProp(projectId, documentId, placementId, {
      attachedCharacterSlot: body.attachedCharacterSlot,
      attachedCharacterId: body.attachedCharacterId,
      relationship: body.relationship as string,
      attachmentPoint: body.attachmentPoint,
    });
    return res.document as unknown as SpatialMapDocument;
  },

  async detachProp(
    projectId: string,
    documentId: string,
    placementId: string,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.detachProp(projectId, documentId, placementId);
    return res.document as unknown as SpatialMapDocument;
  },

  async updatePropRelationship(
    projectId: string,
    documentId: string,
    placementId: string,
    fields: Pick<SpatialPropAttachmentFields, "relationship" | "attachmentPoint">,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.updatePropRelationship(projectId, documentId, placementId, {
      relationship: fields.relationship as string,
      attachmentPoint: fields.attachmentPoint,
    });
    return res.document as unknown as SpatialMapDocument;
  },

  /** CDX-020: bind a Spatial Map document to a project scene explicitly. */
  async assignScene(
    projectId: string,
    documentId: string,
    body: { sceneId: string },
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.assignScene(projectId, documentId, body);
    return res.document as unknown as SpatialMapDocument;
  },

  async createMovement(
    projectId: string,
    documentId: string,
    body?: Record<string, unknown>,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.createMovement(projectId, documentId, body);
    return res.document as unknown as SpatialMapDocument;
  },

  async updateMovement(
    projectId: string,
    documentId: string,
    segmentId: string,
    body: Record<string, unknown>,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.updateMovement(projectId, documentId, segmentId, body);
    return res.document as unknown as SpatialMapDocument;
  },

  async activateMovement(
    projectId: string,
    documentId: string,
    segmentId: string,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.activateMovement(projectId, documentId, segmentId);
    return res.document as unknown as SpatialMapDocument;
  },

  async removeMovement(
    projectId: string,
    documentId: string,
    segmentId: string,
  ): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.removeMovement(projectId, documentId, segmentId);
    return res.document as unknown as SpatialMapDocument;
  },

  async movementArrows(
    projectId: string,
    documentId: string,
    characterId?: string,
  ): Promise<unknown[]> {
    const res = await api.spatialMap.movementArrows(projectId, documentId, characterId);
    return (res as { arrows?: unknown[] }).arrows || [];
  },

  async getSpinCamera(
    projectId: string,
    documentId: string,
  ): Promise<{ placement: SpinCameraPlacement | null; centerStatus: { centered: boolean; distanceMeters: number; toleranceMeters: number } | null }> {
    const res = await api.spatialMap.getSpinCamera(projectId, documentId);
    return {
      placement: (res.placement as SpinCameraPlacement | null) || null,
      centerStatus: (res.centerStatus as { centered: boolean; distanceMeters: number; toleranceMeters: number } | null) || null,
    };
  },

  async placeSpinCamera(
    projectId: string,
    documentId: string,
    body: { x: number; z: number; sceneId?: string | null },
  ): Promise<{ placement: SpinCameraPlacement; centerStatus: { centered: boolean; distanceMeters: number; toleranceMeters: number } }> {
    const res = await api.spatialMap.placeSpinCamera(projectId, documentId, body);
    return {
      placement: res.placement as SpinCameraPlacement,
      centerStatus: res.centerStatus as { centered: boolean; distanceMeters: number; toleranceMeters: number },
    };
  },

  async removeSpinCamera(projectId: string, documentId: string): Promise<void> {
    await api.spatialMap.removeSpinCamera(projectId, documentId);
  },

  async listSpinPackages(projectId: string, documentId: string): Promise<SpinPackageManifest[]> {
    const res = await api.spatialMap.listSpinPackages(projectId, documentId);
    return res.packages ?? res.manifests ?? [];
  },

  async createSpinPackage(
    projectId: string,
    documentId: string,
    body: { provider: string; confirmPaidCloud?: boolean },
  ): Promise<SpinPackageManifest> {
    const res = await api.spatialMap.createSpinPackage(projectId, documentId, body);
    return res.manifest ?? res;
  },

  async getSpinPackage(projectId: string, documentId: string, packageId: string): Promise<SpinPackageManifest> {
    const res = await api.spatialMap.getSpinPackage(projectId, documentId, packageId);
    return res.manifest ?? res;
  },

  async regenerateSpinView(
    projectId: string,
    documentId: string,
    packageId: string,
    direction: SpinViewKey,
    body: { confirmPaidCloud?: boolean } = {},
  ): Promise<SpinPackageManifest> {
    const res = await api.spatialMap.regenerateSpinView(projectId, documentId, packageId, direction, body);
    return res.manifest ?? res;
  },

  async buildErsFromSpinPackage(
    projectId: string,
    documentId: string,
    packageId: string,
  ): Promise<{ ersAssetId: string | null }> {
    const res = await api.spatialMap.buildErsFromSpinPackage(projectId, documentId, packageId);
    return { ersAssetId: res.ersAssetId || res.ers_composite_asset_id || null };
  },

};
