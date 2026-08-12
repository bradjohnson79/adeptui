/**
 * Spatial Map API client — thin typed wrapper over the existing
 * `api.spatialMap` client in `studio-web/src/api.ts`.
 *
 * Reuses the shared client (Law #17 — reuse before rebuild). The grid fields
 * (gridRow/gridColumn/slotIndex/colorKey/miniPrompt/tag) are forwarded via the
 * PATCH placement endpoints by casting through the existing body types,
 * because the frozen M411 contract body types predate the V1 grid extension.
 */
import { api } from "../../../api";
import type {
  SpatialMapCreateBody,
  SpatialMapUpdateBody,
  SpatialMapDocument,
  SpatialCharacterPlacement,
  SpatialPropPlacement,
  SpatialCharacterPlacementBody,
  SpatialCharacterPlacementUpdateBody,
  SpatialPropPlacementBody,
  SpatialPropPlacementUpdateBody,
} from "./types";

export const spatialMapApi = {
  /** Load the most recent Spatial Map document for a project (first in list). */
  async getMostRecentMap(projectId: string): Promise<SpatialMapDocument | null> {
    const res = await api.spatialMap.listMaps(projectId);
    const docs = (res.documents || []) as unknown as SpatialMapDocument[];
    if (!docs.length) return null;
    // Sort by updatedAt desc, fall back to createdAt.
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

  async createMap(projectId: string, body: SpatialMapCreateBody): Promise<SpatialMapDocument> {
    const res = await api.spatialMap.createMap(projectId, body);
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
      // Cast: frozen contract body omits V1 grid fields; backend placement
      // model has them with defaults, so create without grid then PATCH grid.
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

  /** Type guards for narrowing the union-free document. */
  isCharacterPlacement(p: SpatialCharacterPlacement | SpatialPropPlacement): p is SpatialCharacterPlacement {
    return (p as SpatialCharacterPlacement).characterId !== undefined;
  },
};
