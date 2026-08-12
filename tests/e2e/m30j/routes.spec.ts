/**

 * M3.0j — Primary route smoke skeleton

 * @DETERMINISTIC — shell load only; no GPU / generation chains

 */

import { test, expect } from "@playwright/test";

import fs from "node:fs";

import path from "node:path";

import {

  createTempProject,

  deleteProject,

  waitForAppReady,

} from "../helpers/app";



const OUT = path.join("artifacts", "m30j", "playwright");



type RouteCase = {

  id: string;

  path: string | ((projectId: string) => string);

  assert: (page: import("@playwright/test").Page) => Promise<void>;

};



const PRIMARY_ROUTES: RouteCase[] = [

  {

    id: "ROUTE-01",

    path: "/",

    assert: async (page) => {

      await expect(page.getByTestId("create-project-open")).toBeVisible({

        timeout: 30_000,

      });

    },

  },

  {

    id: "ROUTE-02",

    path: (id) => `/project/${id}`,

    assert: async (page) => {

      await expect(page.locator("body")).toBeVisible();

    },

  },

  {

    id: "ROUTE-03",

    path: "/co-director",

    assert: async (page) => {

      await expect(page.locator("#root")).not.toBeEmpty();

    },

  },

  {

    id: "ROUTE-04",

    path: "/source-manager",

    assert: async (page) => {

      await expect(page.locator("body")).toBeVisible();

    },

  },

  {

    id: "ROUTE-05",

    path: (id) => `/project/${id}?workspace=setup`,

    assert: async (page) => {

      await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 45_000 });

    },

  },

  {

    id: "ROUTE-06",

    path: (id) => `/project/${id}?workspace=director`,

    assert: async (page) => {

      await expect(page.locator("body")).toBeVisible();

    },

  },

  {

    id: "ROUTE-07",

    path: (id) => `/project/${id}?workspace=editor`,

    assert: async (page) => {

      await expect(page.locator("body")).toBeVisible();

    },

  },

  {

    id: "ROUTE-08",

    path: (id) => `/project/${id}?workspace=library`,

    assert: async (page) => {

      await expect(page.getByRole("heading", { name: /^Libraries$/i })).toBeVisible({

        timeout: 30_000,

      });

    },

  },

];



test.describe("M3.0j Primary routes @DETERMINISTIC", () => {

  test.beforeAll(async ({ request }) => {

    await waitForAppReady(request);

  });



  for (const route of PRIMARY_ROUTES) {

    test(`${route.id} loads ${typeof route.path === "string" ? route.path : "project workspace"}`, async ({

      page,

      request,

    }) => {

      const needsProject = typeof route.path === "function";

      let projectId: string | undefined;

      if (needsProject) {

        const project = await createTempProject(request, `M30J ${route.id} ${Date.now()}`);

        projectId = project.id;

      }

      try {

        const target = typeof route.path === "string" ? route.path : route.path(projectId!);

        await page.goto(target);

        await page.waitForLoadState("domcontentloaded");

        await route.assert(page);



        fs.mkdirSync(OUT, { recursive: true });

        fs.writeFileSync(

          path.join(OUT, `${route.id.toLowerCase()}.json`),

          JSON.stringify({ id: route.id, path: target, ok: true, mode: "DETERMINISTIC" }, null, 2),

        );

      } finally {

        if (projectId) await deleteProject(request, projectId);

      }

    });

  }



  test.skip("ROUTE-09 production-suite shell — REAL_LOCAL when M2.9 flags off", async () => {

    // Flag-gated; see codirector/production-suite-m29.spec.ts for full matrix.

  });

});


