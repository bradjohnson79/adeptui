import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { expect, type APIRequestContext } from "@playwright/test";
import { API, createTempProject } from "./app";

export const HITCHHIKER_PROJECT_ID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9";
export const HITCHHIKER_LTX_SCENE_ID = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f";
export const HITCHHIKER_IMAGE_A = "d523d406-ce9a-4073-87db-f5ddd06816d1";
export const HITCHHIKER_DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a";
export const EVIDENCE_ROOT = path.join("artifacts", "m32f", "hitchhiker-production-lifecycle");

export function apiBase() {
  // Prefer explicit base; otherwise reuse the shared E2E API helper (respects STUDIO_API_PORT).
  return process.env.STUDIO_API_BASE || API;
}
type JobState = {
  id: string;
  status?: string;
  state?: string;
  message?: string;
  output_path?: string | null;
  outputPath?: string | null;
  [key: string]: unknown;
};

export async function waitForJob(
  request: APIRequestContext,
  jobId: string,
  { timeoutMs = 120_000 }: { timeoutMs?: number } = {},
) {
  const deadline = Date.now() + timeoutMs;
  let last: JobState | null = null;
  while (Date.now() < deadline) {
    const response = await request.get(`${apiBase()}/api/jobs/${encodeURIComponent(jobId)}`);
    if (response.ok()) {
      last = (await response.json()) as JobState;
      const state = String(last.status || last.state || "").toLowerCase();
      if (["done", "failed", "cancelled"].includes(state)) return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for job ${jobId}${last ? ` (last state: ${last.status || last.state})` : ""}`);
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
        "format=duration,size,format_name:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        filePath,
      ],
      {
        windowsHide: true,
      },
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

async function assertPlayable(pathname: string, streamType: "video" | "audio") {
  expect(fs.existsSync(pathname), `${pathname} exists`).toBeTruthy();
  expect(fs.statSync(pathname).size, `${pathname} is non-empty`).toBeGreaterThan(1024);
  const probe = await ffprobeJson(pathname);
  expect(probe, `${pathname} is ffprobe-readable`).not.toBeNull();
  const streams = Array.isArray(probe?.streams) ? probe.streams : [];
  expect(
    streams.some((stream) => (stream as { codec_type?: string }).codec_type === streamType),
    `${pathname} contains a ${streamType} stream`,
  ).toBeTruthy();
  const format = probe?.format as { duration?: string | number } | undefined;
  expect(Number(format?.duration), `${pathname} has duration`).toBeGreaterThan(0);
  return probe;
}

export function assertPlayableVideo(pathname: string) {
  return assertPlayable(pathname, "video");
}

export function assertPlayableAudio(pathname: string) {
  return assertPlayable(pathname, "audio");
}

export function shotDir(name: string) {
  const dir = path.join(EVIDENCE_ROOT, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function isRealLocalEnabled() {
  return process.env.ADEPT_M32F_REAL_LOCAL === "1";
}

export async function ensureHitchhikerProject(request: APIRequestContext) {
  const canonical = await request.get(`${apiBase()}/api/projects/${HITCHHIKER_PROJECT_ID}`);
  if (canonical.ok()) return { ...(await canonical.json()), isCanonical: true, isTemporary: false };
  if (isRealLocalEnabled()) {
    throw new Error(
      `ADEPT_M32F_REAL_LOCAL=1 requires canonical Hitchhiker project ${HITCHHIKER_PROJECT_ID}; GET returned ${canonical.status()}.`,
    );
  }

  const listResponse = await request.get(`${apiBase()}/api/projects`);
  if (listResponse.ok()) {
    const payload = await listResponse.json();
    const projects = Array.isArray(payload) ? payload : payload.projects;
    const existing = Array.isArray(projects)
      ? projects.find((project: { name?: string }) => /hitchhiker/i.test(project.name || ""))
      : undefined;
    if (existing?.id) return { ...existing, isCanonical: false, isTemporary: false };
  }

  const project = await createTempProject(request, "M32F Hitchhiker Shell");
  const scenesRes = await request.get(`${API}/api/projects/${project.id}/scenes`);
  let scenes = scenesRes.ok() ? await scenesRes.json() : [];
  if (!Array.isArray(scenes) || scenes.length === 0) {
    await request.post(`${API}/api/projects/${project.id}/scenes`, {
      data: {
        name: "Hitchhiker opening",
        prompt: "A lone hitchhiker waits beside a quiet rural highway at golden hour.",
      },
    });
    const again = await request.get(`${API}/api/projects/${project.id}/scenes`);
    scenes = again.ok() ? await again.json() : [];
  }
  const scene = Array.isArray(scenes) ? scenes[0] : undefined;
  if (scene?.id) {
    await request.patch(`${API}/api/projects/${project.id}/scenes/${scene.id}`, {
      data: {
        name: "Hitchhiker opening",
        prompt: "A lone hitchhiker waits beside a quiet rural highway at golden hour.",
      },
    });
  }
  return { ...project, isCanonical: false, isTemporary: true };
}
