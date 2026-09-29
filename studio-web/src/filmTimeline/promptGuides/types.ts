export type PromptPreset = {
  id: string;
  category: string;
  label: string;
  description: string;
  promptFragment: string;
  /** Short clause used when a lens is combined with a shot. */
  look?: string;
  fov?: number;
  crop?: number;
  palette?: [string, string, string];
};

export type HelperKind = "scene" | "camera" | "lighting";

export type HelperMemory = Partial<Record<HelperKind, string>>;
