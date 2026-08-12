import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { expect, type APIRequestContext } from "@playwright/test";
import { API } from "./app";

export const HITCHHIKER_PROJECT_ID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9";
export const HITCHHIKER_LTX_SCENE_ID = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f";
export const HITCHHIKER_TEST2_SCENE_ID = "e277e621-189d-471e-b435-f01620f03d0d";
export const HITCHHIKER_IMAGE_B = "9c8848ca-a431-418b-9ddb-ce109ceff07c";
export const HITCHHIKER_DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a";
export const HITCHHIKER_EQUIRECT = "ca5f09c0-3273-4105-8d71-da3a919e43fc";
export const EVIDENCE_ROOT = path.join("artifacts", "m32g", "hitchhiker-test-2");

export function apiBase() {
  return process.env.STUDIO_API_BASE || API;
}

export function isRealLocalEnabled() {
  return process.env.ADEPT_M32G_REAL_LOCAL === "1";
}

/** Scene spatial GET wraps the map under `doc` (v2 SpatialSceneDoc). */
export function spatialDoc(spatial: Record<string, unknown>) {
  const doc = (spatial.doc || spatial) as Record<string, unknown>;
  return doc;
}

export function shotDir(name: string) {
  const dir = path.join(EVIDENCE_ROOT, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export async function waitForJob(
  request: APIRequestContext,
  jobId: string,
  { timeoutMs = 600_000 }: { timeoutMs?: number } = {},
) {
  const deadline = Date.now() + timeoutMs;
  let last: Record<string, unknown> | null = null;
  while (Date.now() < deadline) {
    const response = await request.get(`${apiBase()}/api/jobs/${encodeURIComponent(jobId)}`);
    if (response.ok()) {
      last = (await response.json()) as Record<string, unknown>;
      const state = String(last.status || last.state || "").toLowerCase();
      if (["done", "failed", "cancelled"].includes(state)) return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timed out waiting for job ${jobId}`);
}

export async function ffprobeJson(filePath: string) {
  if (!fs.existsSync(filePath)) return null;
  return new Promise<Record<string, unknown> | null>((resolve) => {
    const child = spawn(
      "ffprobe",
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name:stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate",
        "-of",
        "json",
        filePath,
      ],
      { windowsHide: true },
    );
    let stdout = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.on("error", () => resolve(null));
    child.on("close", (code) => {
      if (code !== 0) return resolve(null);
      try {
        resolve(JSON.parse(stdout) as Record<string, unknown>);
      } catch {
        resolve(null);
      }
    });
  });
}

export async function assertPlayableVideo(pathname: string) {
  expect(fs.existsSync(pathname), `${pathname} exists`).toBeTruthy();
  expect(fs.statSync(pathname).size).toBeGreaterThan(1024);
  const probe = await ffprobeJson(pathname);
  expect(probe).not.toBeNull();
  const streams = Array.isArray(probe?.streams) ? probe!.streams : [];
  expect(streams.some((s) => (s as { codec_type?: string }).codec_type === "video")).toBeTruthy();
  const format = probe?.format as { duration?: string | number } | undefined;
  expect(Number(format?.duration)).toBeGreaterThan(0);
  return probe;
}

export async function assertPlayableAudio(pathname: string) {
  expect(fs.existsSync(pathname), `${pathname} exists`).toBeTruthy();
  const probe = await ffprobeJson(pathname);
  expect(probe).not.toBeNull();
  const streams = Array.isArray(probe?.streams) ? probe!.streams : [];
  expect(streams.some((s) => (s as { codec_type?: string }).codec_type === "audio")).toBeTruthy();
  return probe;
}
