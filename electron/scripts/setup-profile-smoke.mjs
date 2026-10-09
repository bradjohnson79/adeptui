/**
 * Packaged Setup checks. They talk to the disposable Studio API on 8760.
 * They do not start, stop, or download ComfyUI.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const OFFICIAL_COMFY_DOWNLOAD = "https://www.comfy.org/download";

async function call(baseUrl, method, route, body) {
  const response = await fetch(`${baseUrl}${route}`, {
    method,
    headers: body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(60000),
  });
  const text = await response.text();
  let json = null;
  try { json = JSON.parse(text); } catch { json = null; }
  return { status: response.status, json, text };
}

function neededIds(status) {
  const rows = status?.firstRunScan?.essentialNeeded;
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => String(row?.id || ""));
}

export function evaluateSetupProbes({
  apiStatus,
  localStatus,
  hybridStatus,
  prerequisite,
  rejectedStatus,
  connected,
  connectedBytesSame,
  comfyJobStatus,
}) {
  const healthy = prerequisite?.healthy === true;
  const apiNeeded = neededIds(apiStatus);
  const localNeeded = neededIds(localStatus);
  const hybridNeeded = neededIds(hybridStatus);
  const comfyJobAbsent = comfyJobStatus === 404;
  const downloadOk = prerequisite?.downloadUrl === OFFICIAL_COMFY_DOWNLOAD;
  return {
    "API PROFILE OMITS COMFY": apiStatus?.installationProfile === "api" && !apiNeeded.includes("comfyui") ? "PASS" : "FAIL",
    "OFFICIAL COMFY DOWNLOAD URL": downloadOk ? "PASS" : "FAIL",
    "CONNECT REJECTS NON COMFY FOLDER": rejectedStatus === 400 ? "PASS" : "FAIL",
    "CONNECT EXISTING LEAVES FILES": connected?.installed === true && connectedBytesSame === true ? "PASS" : "FAIL",
    "COMFY INSTALL NOT FABRICATED": comfyJobAbsent ? "PASS" : "FAIL",
    "LOCAL REQUIREMENT MATCHES COMFY HEALTH": healthy
      ? (!localNeeded.includes("comfyui") ? "PASS" : "FAIL")
      : (localNeeded.includes("comfyui") ? "PASS" : "FAIL"),
    "HYBRID REQUIREMENT MATCHES COMFY HEALTH": healthy
      ? (!hybridNeeded.includes("comfyui") ? "PASS" : "FAIL")
      : (hybridNeeded.includes("comfyui") ? "PASS" : "FAIL"),
    "COMFY DETECTED WHEN REACHABLE": healthy ? "PRESENT" : "ABSENT",
  };
}

export function rendererShipsComfyPrerequisite(rendererDir) {
  if (!rendererDir || !fs.existsSync(rendererDir)) return false;
  const stack = [rendererDir];
  while (stack.length) {
    const current = stack.pop();
    let entries = [];
    try { entries = fs.readdirSync(current, { withFileTypes: true }); } catch { continue; }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      if (!/\.(js|css|html)$/i.test(entry.name)) continue;
      let text = "";
      try { text = fs.readFileSync(full, "utf8"); } catch { continue; }
      if (text.includes(OFFICIAL_COMFY_DOWNLOAD) && text.includes("Official ComfyUI Download")) return true;
    }
  }
  return false;
}

export async function probePackagedSetup(baseUrl, { tempRoot }) {
  const work = path.join(tempRoot, "comfy-prerequisite-probe");
  fs.rmSync(work, { recursive: true, force: true });
  fs.mkdirSync(work, { recursive: true });
  const missing = path.join(work, "not-comfy");
  const present = path.join(work, "ComfyUI");
  fs.mkdirSync(missing, { recursive: true });
  fs.mkdirSync(present, { recursive: true });
  fs.writeFileSync(path.join(missing, "readme.txt"), "not comfy", "utf8");
  const mainFile = path.join(present, "main.py");
  const original = Buffer.from("print('comfy')\n");
  fs.writeFileSync(mainFile, original);

  const apiSave = await call(baseUrl, "POST", "/api/setup/installation-profile", {
    profile: "api",
    selectedLocalModels: [],
    selectedProviders: ["fal"],
  });
  const prerequisite = await call(baseUrl, "GET", "/api/setup/comfy/prerequisite");
  const rejected = await call(baseUrl, "POST", "/api/setup/comfy/connect", { path: missing });
  const connected = await call(baseUrl, "POST", "/api/setup/comfy/connect", { path: present });
  const connectedBytesSame = fs.readFileSync(mainFile).equals(original);
  const localSave = await call(baseUrl, "POST", "/api/setup/installation-profile", {
    profile: "local",
    selectedLocalModels: [],
    selectedProviders: [],
  });
  const comfyJob = await call(baseUrl, "GET", "/api/setup/components/comfyui/install-job");
  const hybridSave = await call(baseUrl, "POST", "/api/setup/installation-profile", {
    profile: "hybrid",
    selectedLocalModels: ["zimage_models"],
    selectedProviders: ["fal"],
  });

  const gates = evaluateSetupProbes({
    apiStatus: apiSave.json,
    localStatus: localSave.json,
    hybridStatus: hybridSave.json,
    prerequisite: prerequisite.json,
    rejectedStatus: rejected.status,
    connected: connected.json,
    connectedBytesSame,
    comfyJobStatus: comfyJob.status,
  });
  return {
    gates,
    evidence: {
      apiStatus: apiSave.status,
      localStatus: localSave.status,
      hybridStatus: hybridSave.status,
      prerequisite: prerequisite.json,
      rejected: rejected.status,
      connected: connected.status,
      connectedBytesSame,
      comfyJob: comfyJob.status,
    },
  };
}

async function main() {
  const baseIndex = process.argv.indexOf("--base");
  const tempIndex = process.argv.indexOf("--temp");
  if (baseIndex < 0 || tempIndex < 0) return;
  const result = await probePackagedSetup(process.argv[baseIndex + 1], { tempRoot: process.argv[tempIndex + 1] });
  console.log(JSON.stringify(result, null, 2));
  const failed = Object.entries(result.gates).filter(([, value]) => value === "FAIL");
  if (failed.length) process.exitCode = 1;
}

const invoked = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invoked) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
