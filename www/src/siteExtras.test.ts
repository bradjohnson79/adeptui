import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { kofi } from "./support";

const client = [
  "src/components/KoFiButton.tsx",
  "src/components/ContactForm.tsx",
  "src/components/ContactPage.tsx",
  "src/components/Navigation.tsx",
  "src/contact.ts",
  "src/main.tsx",
]
  .map((file) => readFileSync(file, "utf8"))
  .join("\n");

describe("support and contact boundaries", () => {
  it("uses one Ko-fi link and does not inject the widget script", () => {
    const button = readFileSync("src/components/KoFiButton.tsx", "utf8");
    expect(kofi.url).toBe("https://ko-fi.com/G1G728D4FV");
    expect(button).toContain("kofi.url");
    expect(button).not.toContain("kofiwidget2");
    expect(button).not.toContain("storage.ko-fi.com");
    expect(button).not.toContain("<script");
    expect(readFileSync("src/components/Navigation.tsx", "utf8").match(/<KoFiButton \/>/g)).toHaveLength(2);
  });

  it("keeps mail credentials off the browser", () => {
    expect(client).not.toContain("RESEND_API_KEY");
    expect(client).not.toContain("CONTACT_TO");
    expect(client).not.toContain("CONTACT_FROM");
    expect(client).not.toContain("CONTACT_WEBHOOK_URL");
    expect(client).not.toContain("process.env");
    expect(client).not.toMatch(/sk-[a-zA-Z0-9]/);
  });

  it("publishes the contact route", () => {
    expect(readFileSync("src/main.tsx", "utf8")).toContain('path === "/contact"');
    const vercel = readFileSync("vercel.json", "utf8");
    expect(vercel).toContain('"/contact"');
  });
});
