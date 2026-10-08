import { describe, expect, it } from "vitest";
import {
  allowContact,
  contactTransport,
  handleContact,
  readContactConfig,
  resendRequest,
  resetContactRateLimit,
  webhookRequest,
  type ContactConfig,
  type OutboundMail,
} from "./contact";

const ready: ContactConfig = {
  destinationEmail: "studio@example.com",
  fromEmail: "site@example.com",
  webhookUrl: "",
  resendKey: "re_test_key",
  provider: "resend",
};

function valid(overrides: Record<string, unknown> = {}) {
  return {
    name: "Ada Lovelace",
    email: "ada@example.com",
    category: "general",
    subject: "A question about Beta",
    message: "Where can I follow the project?",
    company: "",
    ...overrides,
  };
}

describe("contact delivery configuration", () => {
  it("stays unconfigured until a provider and destination are set", () => {
    expect(contactTransport(readContactConfig({}))).toBe("unconfigured");
    expect(contactTransport({ ...ready, provider: "", resendKey: "" })).toBe("unconfigured");
    expect(contactTransport(ready)).toBe("resend");
  });

  it("keeps the provider secret out of the message body", () => {
    const mail: OutboundMail = { subject: "[Adept UI] General Inquiry — Hello", text: "Hello", replyTo: "ada@example.com" };
    const request = resendRequest(ready, mail);
    const body = String(request.init.body);
    expect(request.url).toBe("https://api.resend.com/emails");
    expect(body).not.toContain(ready.resendKey);
    expect(body).toContain("studio@example.com");
    expect(body).toContain("ada@example.com");
    const webhook = webhookRequest(
      { ...ready, provider: "webhook", webhookUrl: "https://hooks.example/contact" },
      mail,
    );
    expect(webhook?.url).toBe("https://hooks.example/contact");
    expect(webhookRequest({ ...ready, webhookUrl: "http://hooks.example/contact" }, mail)).toBeNull();
  });
});

describe("contact submission", () => {
  it("sends each category with a sortable subject", async () => {
    const sent: OutboundMail[] = [];
    const cases = [
      { category: "general", subject: "Hello", expected: "[Adept UI] General Inquiry — Hello", message: "Thanks — your message has been sent." },
      { category: "bug", subject: "Preview froze", expected: "[Adept UI Bug] Preview froze", message: "Thanks for reporting the issue." },
      { category: "media", subject: "Interview", expected: "[Adept UI Media] Interview", message: "Thanks — your media request has been received." },
    ];
    for (const item of cases) {
      resetContactRateLimit();
      const result = await handleContact(valid({ category: item.category, subject: item.subject, version: "Beta", os: "Windows" }), {
        clientKey: item.category,
        config: ready,
        deliver: async (mail) => {
          sent.push(mail);
          return true;
        },
      });
      expect(result.status).toBe(200);
      expect(result.delivered).toBe(true);
      expect(result.body.message).toBe(item.message);
      expect(sent.at(-1)?.subject).toBe(item.expected);
    }
    const bug = sent.find((mail) => mail.subject.includes("Preview froze"));
    expect(bug?.text).toContain("Adept UI version: Beta");
    expect(bug?.text).toContain("Operating system: Windows");
    const general = sent[0];
    expect(general?.text).not.toContain("Adept UI version");
  });

  it("rejects invalid fields and keeps a configured mailbox from being required for validation", async () => {
    resetContactRateLimit();
    const missing = await handleContact(valid({ email: "not-an-email", category: "nope", subject: "", message: "" }), {
      clientKey: "invalid",
      config: ready,
      deliver: async () => true,
    });
    expect(missing.status).toBe(400);
    expect(missing.body.message).toBe("Enter a valid email address.");
    expect(missing.delivered).toBe(false);
  });

  it("does not deliver a honeypot submission", async () => {
    resetContactRateLimit();
    let called = false;
    const result = await handleContact(valid({ company: "spam co" }), {
      clientKey: "spam",
      config: ready,
      deliver: async () => {
        called = true;
        return true;
      },
    });
    expect(result.status).toBe(200);
    expect(result.delivered).toBe(false);
    expect(called).toBe(false);
  });

  it("rate limits repeated submissions", async () => {
    resetContactRateLimit();
    const key = "repeat";
    for (let count = 0; count < 8; count += 1) expect(allowContact(key, 1_000)).toBe(true);
    expect(allowContact(key, 1_000)).toBe(false);
    const result = await handleContact(valid(), {
      clientKey: key,
      now: 1_000,
      config: ready,
      deliver: async () => true,
    });
    expect(result.status).toBe(429);
    expect(result.body.message).toBe("Please wait a moment and try again.");
  });

  it("reports failure when mail is not configured and when delivery fails", async () => {
    resetContactRateLimit();
    const unconfigured = await handleContact(valid(), {
      clientKey: "none",
      config: readContactConfig({}),
      deliver: async () => true,
    });
    expect(unconfigured.status).toBe(503);
    expect(unconfigured.body.message).toBe("We couldn't send your message right now. Please try again.");
    expect(unconfigured.delivered).toBe(false);

    resetContactRateLimit();
    const failed = await handleContact(valid(), {
      clientKey: "fail",
      config: ready,
      deliver: async () => false,
    });
    expect(failed.status).toBe(502);
    expect(failed.body.message).toBe("We couldn't send your message right now. Please try again.");
  });
});
