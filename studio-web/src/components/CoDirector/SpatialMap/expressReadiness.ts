export type ExpressGenerationMethod = "api";

export const ENV_DESCRIPTION_HELP =
  "Describe the environment you want to use for your Spatial Map. Include important rooms, corridors, doors, entrances, elevators, approximate dimensions, landmarks, or other spatial details you want Co-Director to preserve. If you add a reference image, Co-Director will also use the visible design and environment characteristics from that image.";

export const GPT_REQUIRED_MESSAGE =
  "GPT Image 2 is required for Spatial Map generation. Configure GPT Image 2 in your API settings to continue.";

export const API_NEEDS_SOURCE = "Add an environment description or reference image.";
export const API_NEEDS_GPT = GPT_REQUIRED_MESSAGE;

export const EXPRESS_FAILURE_PRESERVE =
  "Spatial Map generation failed. Your description and reference have been preserved.";

export const USE_AS_ATLAS_HELP =
  "Check this if the selected image is already a finished roofless top-down Spatial Map / Atlas. Adept will skip generation and open it directly for character, prop, and camera placement.";

export const DIRECT_USE_NOT_ATLAS =
  "This image does not appear to be a finished top-down Spatial Map / Atlas. Uncheck “Use this image as the Spatial Map” to use it as a reference for GPT Image 2 instead.";

export const DIRECT_USE_NEEDS_IMAGE = "Select or upload an image first.";

export function expressGenerateReadiness(input: {
  gptConfigured: boolean | null;
  description: string;
  referenceAssetId: string;
  useAsAtlas?: boolean;
}): { ok: boolean; reason: string | null } {
  const hasRef = Boolean(input.referenceAssetId.trim());
  const hasDesc = Boolean(input.description.trim());
  if (input.useAsAtlas) {
    if (!hasRef) return { ok: false, reason: DIRECT_USE_NEEDS_IMAGE };
    return { ok: true, reason: null };
  }
  if (input.gptConfigured !== true) {
    return { ok: false, reason: API_NEEDS_GPT };
  }
  if (!hasDesc && !hasRef) {
    return { ok: false, reason: API_NEEDS_SOURCE };
  }
  return { ok: true, reason: null };
}

export function expressProgressMessage(stage: string, message: string): string {
  const blob = `${stage} ${message}`.toLowerCase();
  if (/\b(complete|completed|done)\b/.test(blob)) return "Complete";
  if (/\bfail/.test(blob)) return message || stage || "Failed";
  if (/\bcancel/.test(blob)) return "Cancelled";
  if (blob.includes("design")) return "Designing Environment";
  if (blob.includes("validat")) return "Validating Atlas";
  if (blob.includes("sav")) return "Saving Spatial Map";
  if (blob.includes("gpt") || blob.includes("generat") || blob.includes("atlas")) {
    return "Generating Atlas with GPT Image 2";
  }
  if (blob.includes("queued") || blob.includes("prepar")) return "Preparing Spatial Map";
  return message || stage || "Preparing Spatial Map";
}
