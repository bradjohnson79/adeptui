/** Owner Schnick / Korri must not be used as destructive fixtures. */

export const SCHNICK_PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
export const KORRI_CHARACTER_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
export const CERT_PROJECT_NAME = "Adept Stability Cert";

export function assertNotOwnerWriteTarget(projectId: string, characterId?: string): void {
  if (projectId === SCHNICK_PROJECT_ID) {
    throw new Error("Destructive tests must not write Schnick Coffee. Use ADEPT_CERT_PROJECT_ID.");
  }
  if (characterId && characterId === KORRI_CHARACTER_ID) {
    throw new Error("Destructive tests must not mutate Korri persist CRS.");
  }
}

export function creatorUiBase(): string {
  const raw = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
  if (raw.includes(":8760")) {
    throw new Error("Retired :8760 is not the creator UI. Use http://127.0.0.1:5173 or hosted Vercel.");
  }
  return raw;
}

export function studioApiBase(): string {
  return process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
}
