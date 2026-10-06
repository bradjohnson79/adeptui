import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "CoDirectorMessage.tsx"), "utf8");

describe("CoDirectorMessage execution stop", () => {
  it("wires Stop this on the drawer execution card to cancelExecution", () => {
    expect(src).toContain('data-testid="codirector-exec-stop"');
    expect(src).toContain("api.cancelExecution(projectId, execution.execution_id)");
    expect(src).toContain("Stop this");
    expect(src.match(/<ExecutionSummaryCard/g)?.length).toBeGreaterThanOrEqual(2);
    expect(src).toContain("projectId={uiContext.projectId || \"\"}");
  });
});
