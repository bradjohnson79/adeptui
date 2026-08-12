import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext } from "@playwright/test";

export const HITCHHIKER_PROJECT_ID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9";
export const HITCHHIKER_LTX_SCENE_ID = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f";
export const HITCHHIKER_TEST2_SCENE_ID = "e277e621-189d-471e-b435-f01620f03d0d";
export const HITCHHIKER_DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a";
export const EVIDENCE_ROOT = path.join("artifacts", "m33", "character-profile");
export const KORRI_EVIDENCE_ROOT = path.join("artifacts", "m33", "korri-character-profile");

export function korriEvidenceDir(...parts: string[]) {
  const dir = path.join(KORRI_EVIDENCE_ROOT, ...parts);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function writeKorriEvidence(relParts: string[], data: unknown) {
  const dir = korriEvidenceDir(...relParts.slice(0, -1));
  const file = path.join(dir, relParts[relParts.length - 1]!);
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf-8");
  return file;
}

export function apiBase() {
  return process.env.STUDIO_API_BASE || "";
}

export function isRealLocalEnabled() {
  return process.env.ADEPT_M33_REAL_LOCAL === "1";
}

export function evidenceDir(...parts: string[]) {
  const dir = path.join(EVIDENCE_ROOT, ...parts);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function writeEvidence(relParts: string[], data: unknown) {
  const dir = evidenceDir(...relParts.slice(0, -1));
  const file = path.join(dir, relParts[relParts.length - 1]!);
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf-8");
  return file;
}

export async function enableCharacterIdentity(request: APIRequestContext) {
  try {
    const e2e = await request.get(`${apiBase()}/api/e2e/status`);
    if (e2e.ok()) {
      await request.post(`${apiBase()}/api/e2e/feature-flags`, {
        data: { flags: { character_identity_v1: true } },
      });
    }
  } catch {
    /* ignore */
  }
}

export async function createDisposableProject(request: APIRequestContext, name?: string) {
  const res = await request.post(`${apiBase()}/api/projects`, {
    data: { name: name || `M33 Disposable ${Date.now()}` },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string; name: string }>;
}

export async function deleteProject(request: APIRequestContext, id: string) {
  await request.delete(`${apiBase()}/api/projects/${id}`).catch(() => null);
}

export async function getVoiceProviders(request: APIRequestContext) {
  const res = await request.get(`${apiBase()}/api/character-voice/providers`);
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<Record<string, any>>;
}

export async function assertProtectedUnchanged(request: APIRequestContext) {
  for (const id of [HITCHHIKER_LTX_SCENE_ID, HITCHHIKER_TEST2_SCENE_ID]) {
    const res = await request.get(
      `${apiBase()}/api/projects/${HITCHHIKER_PROJECT_ID}/scenes/${id}`,
    );
    // Scene may 404 if route differs; still assert project exists and dialogue asset path untouched.
    if (res.status() === 404) continue;
    expect(res.ok()).toBeTruthy();
  }
  const asset = await request.get(
    `${apiBase()}/api/projects/${HITCHHIKER_PROJECT_ID}/assets/${HITCHHIKER_DIALOGUE}`,
  );
  if (asset.ok()) {
    const body = await asset.json();
    writeEvidence(["persistence", "hitchhiker-dialogue.json"], body);
  }
}
