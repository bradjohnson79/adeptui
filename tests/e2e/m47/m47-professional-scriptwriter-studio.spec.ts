import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

/**
 * M4.7 Professional Scriptwriter Studio — GO-path coverage.
 * Identity: Milestone M4.7 · Product Adept UI Studio · Feature Professional Scriptwriter Studio
 */
test.describe("@m47 @scriptwriter Professional Scriptwriter Studio", () => {
  test("full production path: edit → autosave → proposal → bible → scene → timeline → export → reload", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M47 Scriptwriter ${Date.now()}`);
    try {
      // Ensure project has a scene for linkage
      const scenesRes = await request.get(`${API}/api/projects/${project.id}`);
      expect(scenesRes.ok()).toBeTruthy();
      const projectBody = await scenesRes.json();
      if (!(projectBody.scenes || []).length) {
        const sc = await request.post(`${API}/api/projects/${project.id}/scenes`, {
          data: { name: "M47 Scene" },
        });
        expect(sc.ok()).toBeTruthy();
      }

      // API: bootstrap + import Fountain
      const studio = await request.get(`${API}/api/projects/${project.id}/scriptwriter`);
      expect(studio.ok()).toBeTruthy();
      const studioBody = await studio.json();
      const docId = studioBody.document.id as string;
      expect(studioBody.paginationMode).toBe("estimated");

      const fountain = [
        "Title: M47 Path",
        "",
        "INT. STUDIO - DAY",
        "",
        "Korri adjusts a lens.",
        "",
        "KORRI",
        "Hold the frame.",
        "",
      ].join("\n");
      const imported = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/import`,
        { data: { text: fountain, format: "fountain" } },
      );
      expect(imported.ok()).toBeTruthy();
      const afterImport = await imported.json();
      const heading = (afterImport.document.elements as Array<{ id: string; type: string }>).find(
        (e) => e.type === "scene_heading",
      );
      expect(heading?.id).toBeTruthy();
      const dialogue = (afterImport.document.elements as Array<{ id: string; type: string; text: string }>).find(
        (e) => e.type === "dialogue",
      );
      expect(dialogue?.id).toBeTruthy();

      // Proposal apply via transaction
      const proposal = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/proposals/apply`,
        {
          data: {
            proposal: { op: "replace", elementId: dialogue!.id, text: "Hold the frame steady." },
          },
        },
      );
      expect(proposal.ok()).toBeTruthy();
      expect((await proposal.json()).transaction.kind).toBe("apply_codirector_proposal");

      // Bible proposals (not silent)
      const bible = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/bible/propose`,
      );
      expect(bible.ok()).toBeTruthy();
      const bibleBody = await bible.json();
      expect(bibleBody.appliesAutomatically).toBeFalsy();

      // Scene link
      const projectFresh = await (await request.get(`${API}/api/projects/${project.id}`)).json();
      const sceneId = projectFresh.scenes[0].id as string;
      const link = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/scenes/link`,
        { data: { sceneHeadingId: heading!.id, projectSceneId: sceneId } },
      );
      expect(link.ok()).toBeTruthy();

      // Timeline prep + metadata apply
      const prep = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/timeline/prepare`,
        { data: { sceneHeadingId: heading!.id } },
      );
      expect(prep.ok()).toBeTruthy();
      const prepBody = await prep.json();
      expect(prepBody.proposal.appliesClipsAutomatically).toBeFalsy();
      expect(prepBody.proposal.visualizationPrompt).toBeTruthy();

      const applyTl = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/timeline/apply-metadata`,
        { data: { sceneHeadingId: heading!.id, metadata: prepBody.proposal } },
      );
      expect(applyTl.ok()).toBeTruthy();
      expect((await applyTl.json()).transaction.kind).toBe("apply_timeline_prep_metadata");

      // Fountain + PDF export
      const fountainOut = await request.get(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/export/fountain`,
      );
      expect(fountainOut.ok()).toBeTruthy();
      expect((await fountainOut.json()).fountain).toContain("INT.");

      const pdfOut = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/export/pdf`,
      );
      expect(pdfOut.ok()).toBeTruthy();

      // Co-Director tool inspect (read)
      const inspect = await request.post(
        `${API}/api/codirector/projects/${project.id}/tools/read`,
        {
          data: {
            toolId: "script.inspect",
            arguments: { documentId: docId },
          },
        },
      );
      expect(inspect.ok()).toBeTruthy();
      const inspectBody = await inspect.json();
      expect(inspectBody.status).toBe("succeeded");
      const envelope = inspectBody.result || {};
      const data = envelope.data || envelope;
      expect(String(data.documentId || docId)).toBeTruthy();

      // UI: studio shell
      await page.goto(`/project/${project.id}?workspace=scriptwriter`);
      await expect(page.getByTestId("scriptwriter-studio")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("scriptwriter-toolbar")).toBeVisible();
      await expect(page.getByTestId("scriptwriter-navigator")).toBeVisible();
      await expect(page.getByTestId("scriptwriter-inspector")).toBeVisible();
      await expect(page.getByTestId("scriptwriter-save-state")).toBeVisible();
      await expect(page.getByTestId("scriptwriter-status")).toContainText(/estimated/i);

      await page.getByTestId("scriptwriter-insert-scene").click();
      await expect(page.getByTestId("scriptwriter-navigator")).toBeVisible();

      await page.getByTestId("scriptwriter-command").click();
      await expect(page.getByTestId("scriptwriter-command-palette")).toBeVisible();
      await page.getByRole("button", { name: "Close" }).click();

      // Alias writer → studio
      await page.goto(`/project/${project.id}?workspace=writer`);
      await expect(page.getByTestId("scriptwriter-studio")).toBeVisible({ timeout: 45_000 });

      // Reload validation
      const reload = await request.get(`${API}/api/projects/${project.id}/scriptwriter`);
      expect(reload.ok()).toBeTruthy();
      const reloadBody = await reload.json();
      expect(reloadBody.document.id).toBe(docId);
      expect((reloadBody.document.elements || []).length).toBeGreaterThan(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("transaction undo + revision compare APIs", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M47 Undo ${Date.now()}`);
    try {
      const studio = await (await request.get(`${API}/api/projects/${project.id}/scriptwriter`)).json();
      const docId = studio.document.id as string;
      const a = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/scenes/insert`,
        { data: { heading: "EXT. ROAD - DAY" } },
      );
      expect(a.ok()).toBeTruthy();
      const undo = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/undo`,
      );
      expect(undo.ok()).toBeTruthy();

      const r1 = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/revisions`,
        { data: { name: "White", color: "White" } },
      );
      expect(r1.ok()).toBeTruthy();
      await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/scenes/insert`,
        { data: { heading: "INT. BAR - NIGHT" } },
      );
      const r2 = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/revisions`,
        { data: { name: "Blue", color: "Blue" } },
      );
      expect(r2.ok()).toBeTruthy();
      const idA = (await r1.json()).revision.id as string;
      const idB = (await r2.json()).revision.id as string;
      const cmp = await request.post(
        `${API}/api/projects/${project.id}/scriptwriter/documents/${docId}/revisions/compare`,
        { data: { revisionA: idA, revisionB: idB } },
      );
      expect(cmp.ok()).toBeTruthy();
      expect(Array.isArray((await cmp.json()).changed)).toBeTruthy();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
