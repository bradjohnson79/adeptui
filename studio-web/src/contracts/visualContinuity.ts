/** M4.8 Visual Continuity Session — shared with studio-api/app/image_studio/continuity.py */

export type VisualContinuitySession = {
  id: string;
  projectId: string;
  sceneId?: string;
  characterIds: string[];
  locationIds: string[];
  costumeIds: string[];
  projectStyleVersion?: string;
  referenceAssetIds: string[];
  approvedImageIds: string[];
  lightingDirection?: string;
  colorTreatment?: string;
  lensLanguage?: string;
  aspectRatio?: string;
  visualEra?: string;
  productionStyle?: string;
  createdAt: string;
  updatedAt: string;
};
