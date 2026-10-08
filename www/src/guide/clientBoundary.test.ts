import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const client = [
  "src/guide/GuideDock.tsx",
  "src/guide/messages.ts",
  "src/styles/guide.css",
  "src/main.tsx",
]
  .map((file) => readFileSync(file, "utf8"))
  .join("\n");

describe("website guide client boundary", () => {
  it("keeps credentials and the model identifier off the browser", () => {
    expect(client).not.toMatch(/sk-[a-zA-Z0-9]/);
    expect(client).not.toContain("OPENAI_API_KEY");
    expect(client).not.toContain("gpt-5-mini");
    expect(client).not.toContain("api.openai.com");
  });

  it("mounts one dock from the site shell", () => {
    const main = readFileSync("src/main.tsx", "utf8");
    expect(main.match(/<GuideDock \/>/g)).toHaveLength(1);
  });
});
