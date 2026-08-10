import assert from "node:assert/strict";
import test from "node:test";

import { executeAction } from "./execute.ts";

function installStorage() {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem(key: string) {
        return store.has(key) ? store.get(key)! : null;
      },
      setItem(key: string, value: string) {
        store.set(key, value);
      },
      removeItem(key: string) {
        store.delete(key);
      },
      clear() {
        store.clear();
      },
    },
  });
}

function installWindowLocation(pathname: string, search = "", hash = "") {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      location: {
        pathname,
        search,
        hash,
      },
    },
  });
}

test("createProject redirects Co-Director through the shared Home create flow", async () => {
  installStorage();
  installWindowLocation("/co-director", "?projectId=existing-project", "#composer");
  let navigatedTo = "";

  const result = await executeAction(
    "createProject",
    { name: "Dreamweaver" },
    {
      navigate: (path) => {
        navigatedTo = path;
      },
    },
  );

  assert.equal(result.ok, true);
  assert.equal(
    navigatedTo,
    "/?create=1&createName=Dreamweaver&pendingKind=co-director&pendingReturnTo=%2Fco-director%3FprojectId%3Dexisting-project%23composer",
  );
});
