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
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridRow?: number;
  gridColumn?: number;
  /** Optional. Default true. false hides the marker only; assignment and coords stay. */
  visible?: boolean;
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

};
