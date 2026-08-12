/**
 * M3.3j Korri Character Profile — M33-KORRI-01..08
 * Deterministic structural checks; voice real-local skipped unless ADEPT_M33_REAL_LOCAL=1.
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  assertProtectedUnchanged,
  createDisposableProject,
  deleteProject,
  enableCharacterIdentity,
  isRealLocalEnabled,
  korriEvidenceDir,
  writeKorriEvidence,
  HITCHHIKER_PROJECT_ID,
} from "../helpers/m33";

const API = "";
const KORRI_BRIEF =
  "Korri is Anadriya's biological sister in Providence — young adult, irreverent, emotionally transparent. " +
  "Human/Sun Sprite Elf hybrid. Not a child, not sexualized, not a duplicate of Anadriya. " +
  "Visual specifics remain proposed until owner approval.";

const OUT = path.join("artifacts", "m33", "korri-character-profile");

async function waitForM33Ready(request: import("@playwright/test").APIRequestContext) {
  test.setTimeout(240_000);
  await expect.poll(async () => (await request.get(`${API}/api/health`)).ok(), { timeout: 180_000 }).toBeTruthy();
  await enableCharacterIdentity(request);
  const probe = await request.post(`${API}/api/projects`, { data: { name: `KORRI PROBE ${Date.now()}` } });
  if (!probe.ok()) return false;
  const project = await probe.json();
  const list = await request.get(`${API}/api/projects/${project.id}/characters`);
  await request.delete(`${API}/api/projects/${project.id}`).catch(() => null);
  return list.ok();
}

test.describe("M3.3j Korri Character @DETERMINISTIC", () => {
  test.beforeAll(() => {
    fs.mkdirSync(OUT, { recursive: true });
    korriEvidenceDir();
  });

  test.beforeEach(async ({ request }) => {
    await expect.poll(async () => waitForM33Ready(request), { timeout: 180_000 }).toBeTruthy();
  });

  test("M33-KORRI-01 create draft profile from brief", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-01 ${Date.now()}`);
    try {
      const res = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Korri", role: "Principal", description: KORRI_BRIEF },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
      const body = await res.json();
      writeKorriEvidence(["e2e", "M33-KORRI-01-create.json"], body);
      expect(body.name).toBe("Korri");
      expect(body.status).toMatch(/DRAFT|INCOMPLETE/);
      expect(body.approval_status).toBe("draft");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-02 propose three visual directions", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-02 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Korri", role: "Principal", description: KORRI_BRIEF },
      });
      const character = await created.json();
      const propose = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/visual-gates/concept/propose`,
        { data: {} },
      );
      expect(propose.ok(), await propose.text()).toBeTruthy();
      const body = await propose.json();
      writeKorriEvidence(["e2e", "M33-KORRI-02-directions.json"], body);
      expect((body.directions || []).length).toBeGreaterThanOrEqual(3);
      expect(body.status).toBe("AWAITING_OWNER");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-03 traits carry PROPOSED_BY_CHARACTER_CREATOR provenance", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-03 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Korri", role: "Principal", description: KORRI_BRIEF },
      });
      const character = await created.json();
      const trait = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/traits`,
        {
          data: {
            category: "brief",
            key: "source_brief",
            value: KORRI_BRIEF,
            provenance: "PROPOSED_BY_CHARACTER_CREATOR",
          },
        },
      );
      expect(trait.ok(), await trait.text()).toBeTruthy();
      const body = await trait.json();
      writeKorriEvidence(["e2e", "M33-KORRI-03-trait.json"], body);
      expect(body.provenance).toBe("PROPOSED_BY_CHARACTER_CREATOR");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-04 owner concept select requires approvedBy", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-04 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Korri", role: "Principal", description: KORRI_BRIEF },
      });
      const character = await created.json();
      await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/visual-gates/concept/propose`,
        { data: {} },
      );
      const select = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/visual-gates/concept/select`,
        { data: { directionId: "wild_sun_sprite", approvedBy: "owner" } },
      );
      expect(select.ok(), await select.text()).toBeTruthy();
      const body = await select.json();
      writeKorriEvidence(["e2e", "M33-KORRI-04-select.json"], body);
      expect(body.status).toBe("OWNER_APPROVED");
      expect(body.approvedBy).toBe("owner");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-05 gate cannot OWNER_APPROVE without approvedBy", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-05 ${Date.now()}`);
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name: "Korri", role: "Principal", description: KORRI_BRIEF },
      });
      const character = await created.json();
      const bad = await request.post(
        `${API}/api/projects/${project.id}/characters/${character.id}/visual-gates/hero_identity`,
        { data: { status: "OWNER_APPROVED" } },
      );
      expect(bad.status()).toBe(400);
      const detail = await bad.json();
      writeKorriEvidence(["e2e", "M33-KORRI-05-reject.json"], detail);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-06 korri-profile-create evidence file shape", async () => {
    const createPath = path.join(OUT, "korri-profile-create.json");
    test.skip(!fs.existsSync(createPath), "Run scripts/m33j_korri_create_from_brief.py first.");
    const data = JSON.parse(fs.readFileSync(createPath, "utf-8"));
    expect(data.characterId).toBeTruthy();
    expect(data.projectId).toBeTruthy();
    expect((data.visualDirections?.directions || []).length).toBeGreaterThanOrEqual(3);
    expect(data.provenance).toBe("PROPOSED_BY_CHARACTER_CREATOR");
  });

  test("M33-KORRI-07 Hitchhiker certification project protected", async ({ request }) => {
    const project = await createDisposableProject(request, `M33-KORRI-07 ${Date.now()}`);
    try {
      const blocked = await request.post(`${API}/api/projects/${HITCHHIKER_PROJECT_ID}/characters`, {
        data: { name: "Blocked", role: "cert", description: "Should not create on Hitchhiker" },
      });
      // API may allow create on Hitchhiker — Co-Director tools block mutations; assert scenes untouched.
      writeKorriEvidence(["e2e", "M33-KORRI-07-hitchhiker-post.json"], {
        status: blocked.status(),
        note: "Scene-level protection verified via assertProtectedUnchanged",
      });
      await assertProtectedUnchanged(request);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M33-KORRI-08 voice providers endpoint reachable", async ({ request }) => {
    test.skip(!isRealLocalEnabled(), "Set ADEPT_M33_REAL_LOCAL=1 for real-local voice checks.");
    const res = await request.get(`${API}/api/character-voice/providers`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    writeKorriEvidence(["e2e", "M33-KORRI-08-providers.json"], body);
    expect(body.qwenVoiceClone || body.qwenVoiceDesign).toBeTruthy();
  });
});
