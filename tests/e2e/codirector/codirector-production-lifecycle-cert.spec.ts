/**
 * Production lifecycle stage-gate certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/production-lifecycle/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) return { id: forced, name: PROJECT_NAME };
  const res = await request.get(`${API}/api/projects`);
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named).toBeTruthy();
  return named as { id: string; name: string };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta production lifecycle cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("stage gates from story through complete/reopen", async ({ request }) => {
    test.setTimeout(420_000);
    await waitForAppReady(request);
    const project = await resolveProject(request);
    const gates: Record<string, string> = {};
    const base = `${API}/api/codirector/projects/${project.id}/production-lifecycle`;

    await request.put(`${base}/script`, { data: { status: "NONE" } });
    const blockedCast = await request.post(`${base}/casting`, {
      data: { characterName: "Probe", status: "CAST_LOCKED" },
    });
    const blockedBody = await blockedCast.json();
    expect(blockedBody.ok).toBeFalsy();
    gates["No formal casting without script"] =
      blockedBody.error === "NO_FORMAL_CASTING_WITHOUT_SCRIPT" ? "GO" : "FAIL";

    await request.post(`${base}/story-ready`);
    await request.put(`${base}/script`, { data: { status: "DRAFT" } });
    let life = await (await request.get(base)).json();
    gates["Story stage"] = life.lifecycle?.storyReady ? "GO" : "FAIL";
    gates["Script stage"] = life.lifecycle?.scriptStatus === "DRAFT" ? "GO" : "FAIL";

    // Exploratory concept allowed conceptually; cast lock still needs APPROVED
    await request.put(`${base}/script`, { data: { status: "APPROVED" } });
    life = await (await request.get(base)).json();
    gates["Casting workflow"] = ["OPEN", "IN_PROGRESS", "CAST_LOCKED"].includes(
      String(life.lifecycle?.castingStatus),
    )
      ? "GO"
      : "FAIL";

    await request.post(`${base}/casting`, {
      data: { characterName: "Special Agent Barnes", status: "CAST_LOCKED" },
    });
    await request.post(`${base}/casting`, {
      data: { characterName: "Dr. Kyung Leong", status: "CAST_LOCKED" },
    });
    life = await (await request.get(base)).json();
    gates["Cast lock"] = life.lifecycle?.castingStatus === "CAST_LOCKED" ? "GO" : "FAIL";

    await request.put(`${base}/script`, { data: { status: "LOCKED" } });
    const partial = await request.post(`${base}/scenes`, {
      data: {
        scene: {
          sceneId: "sc-gate-1",
          scriptLocked: true,
          requiredCharacters: ["Special Agent Barnes"],
          castReady: true,
          locationReady: false,
          propsReady: true,
          wardrobeReady: true,
          imageReferencesReady: false,
          voiceReady: true,
          audioPlanReady: true,
        },
      },
    });
    const partialBody = await partial.json();
    writeArtifact("scene_partial.json", partialBody);
    gates["Scene readiness"] = partialBody.ok ? "GO" : "FAIL";

    const pkg = await request.get(`${base}/scenes/sc-gate-1/package`);
    const pkgBody = await pkg.json();
    writeArtifact("scene_package_blocked.json", pkgBody);
    gates["Scene Production Package"] =
      !pkgBody.ok && pkgBody.error === "NO_FINAL_GENERATION_WITHOUT_SCENE_READINESS" ? "GO" : "FAIL";

    await request.post(`${base}/scenes`, {
      data: {
        scene: {
          sceneId: "sc-gate-1",
          scriptLocked: true,
          requiredCharacters: ["Special Agent Barnes"],
          castReady: true,
          locationReady: true,
          propsReady: true,
          wardrobeReady: true,
          imageReferencesReady: true,
          voiceReady: true,
          audioPlanReady: true,
        },
      },
    });
    const readyPkg = await (await request.get(`${base}/scenes/sc-gate-1/package`)).json();
    writeArtifact("scene_package_ready.json", readyPkg);
    gates["Production planning"] = readyPkg.ok ? "GO" : "FAIL";

    const tl = await (await request.post(`${base}/timeline-ready`)).json();
    gates["Timeline assembly"] = tl.ok ? "GO" : "FAIL";
    const post = await (await request.post(`${base}/post`, { data: { status: "IN_PROGRESS" } })).json();
    gates["Post-production handoff"] = post.ok ? "GO" : "FAIL";

    const qc = await (await request.post(`${base}/final-qc`, { data: { passed: true } })).json();
    gates["Final QC"] = qc.ok ? "GO" : "FAIL";
    const complete = await (await request.post(`${base}/complete`, { data: { level: "PROJECT" } })).json();
    gates["Project completion"] = complete.ok ? "GO" : "FAIL";
    const reopen = await (await request.post(`${base}/reopen`)).json();
    gates["Completion reopen"] = reopen.ok ? "GO" : "FAIL";

    life = await (await request.get(base)).json();
    writeArtifact("lifecycle_final.json", life);
    gates["Project Bible lifecycle tracking"] = (life.lifecycle?.stageHistory || []).length ? "GO" : "FAIL";
    gates["Stage-aware next steps"] = (life.nextSteps || []).length ? "GO" : "FAIL";

    const doc = await request.post(`${API}/api/projects`, {
      data: { name: `PL-Doc-${Date.now()}`, primary_project_type: "documentary" },
    });
    const docId = String((await doc.json()).id);
    const dlife = await (
      await request.get(`${API}/api/codirector/projects/${docId}/production-lifecycle`)
    ).json();
    writeArtifact("documentary_lifecycle.json", dlife);
    gates["Format-aware exceptions"] =
      dlife.lifecycle?.formatProfile === "documentary" ? "GO" : "FAIL";

    const failed = Object.entries(gates).filter(([, v]) => v !== "GO");
    writeArtifact("cert_gates.json", { gates, failed });
    expect(failed, JSON.stringify(failed)).toEqual([]);
  });
});
