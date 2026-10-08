import { contactCategories, contactCategory, contactFailure, type ContactCategoryId } from "../src/contact";

const windowMs = 10 * 60 * 1000;
const maxRequests = 8;
const hits = new Map<string, number[]>();

export function resetContactRateLimit(): void {
  hits.clear();
}

export function allowContact(key: string, now = Date.now()): boolean {
  const recent = (hits.get(key) ?? []).filter((stamp) => now - stamp < windowMs);
  if (recent.length >= maxRequests) {
    hits.set(key, recent);
    return false;
  }
  recent.push(now);
  hits.set(key, recent);
  return true;
}

export type ContactConfig = {
  destinationEmail: string;
  fromEmail: string;
  webhookUrl: string;
  resendKey: string;
  provider: string;
};

export type OutboundMail = {
  subject: string;
  text: string;
  replyTo: string;
};

export type ContactResult = {
  status: number;
  body: { message: string };
  delivered: boolean;
};

const limits = {
  name: 80,
  email: 120,
  subject: 140,
  message: 4000,
  detail: 60,
};

function withoutControls(value: string, keepNewlines: boolean): string {
  const source = keepNewlines ? value.replace(/\r\n/g, "\n").replace(/\r/g, "\n") : value;
  let text = "";
  for (const char of source) {
    const code = char.charCodeAt(0);
    if (keepNewlines && char === "\n") {
      text += "\n";
      continue;
    }
    if (code < 32 || code === 127) continue;
    text += char;
  }
  return text;
}

function line(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const text = withoutControls(value, false).replace(/\s+/g, " ").trim();
  if (!text || text.length > max) return null;
  return text;
}

function messageText(value: unknown): { text: string } | { error: string } {
  if (typeof value !== "string" || !value.trim()) return { error: "Enter a message." };
  const text = withoutControls(value, true).trim();
  if (!text) return { error: "Enter a message." };
  if (text.length > limits.message) return { error: "Enter a shorter message." };
  return { text };
}

function emailAddress(value: unknown): string | null {
  const text = line(value, limits.email);
  if (!text || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) return null;
  return text;
}

function optionalDetail(value: unknown): string {
  if (typeof value !== "string") return "";
  return withoutControls(value, false).replace(/\s+/g, " ").trim().slice(0, limits.detail);
}

export function readContactConfig(env: NodeJS.ProcessEnv = process.env): ContactConfig {
  return {
    destinationEmail: (env.CONTACT_TO ?? "").trim(),
    fromEmail: (env.CONTACT_FROM ?? "").trim(),
    webhookUrl: (env.CONTACT_WEBHOOK_URL ?? "").trim(),
    resendKey: (env.RESEND_API_KEY ?? "").trim(),
    provider: (env.CONTACT_PROVIDER ?? "").trim().toLowerCase(),
  };
}

function httpsUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function contactTransport(config: ContactConfig): "resend" | "webhook" | "unconfigured" {
  if (config.provider === "webhook" && httpsUrl(config.webhookUrl)) return "webhook";
  if (
    config.provider === "resend" &&
    config.resendKey &&
    emailAddress(config.destinationEmail) &&
    emailAddress(config.fromEmail)
  ) {
    return "resend";
  }
  return "unconfigured";
}

export function resendRequest(config: ContactConfig, mail: OutboundMail): { url: string; init: RequestInit } {
  return {
    url: "https://api.resend.com/emails",
    init: {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.resendKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: config.fromEmail,
        to: [config.destinationEmail],
        reply_to: mail.replyTo,
        subject: mail.subject,
        text: mail.text,
      }),
    },
  };
}

export function webhookRequest(config: ContactConfig, mail: OutboundMail): { url: string; init: RequestInit } | null {
  if (!httpsUrl(config.webhookUrl)) return null;
  return {
    url: config.webhookUrl,
    init: {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: mail.subject,
        text: mail.text,
        replyTo: mail.replyTo,
      }),
    },
  };
}

async function defaultDeliver(config: ContactConfig, mail: OutboundMail): Promise<boolean> {
  const transport = contactTransport(config);
  const request = transport === "resend" ? resendRequest(config, mail) : transport === "webhook" ? webhookRequest(config, mail) : null;
  if (!request) return false;
  const response = await fetch(request.url, request.init);
  return response.ok;
}

function mailBody(input: {
  name: string;
  email: string;
  category: string;
  subject: string;
  message: string;
  version: string;
  os: string;
}): string {
  const lines = [
    `Name: ${input.name}`,
    `Email: ${input.email}`,
    `Category: ${input.category}`,
    `Subject: ${input.subject}`,
  ];
  if (input.version) lines.push(`Adept UI version: ${input.version}`);
  if (input.os) lines.push(`Operating system: ${input.os}`);
  lines.push("", input.message);
  return lines.join("\n");
}

export async function handleContact(
  input: unknown,
  options: {
    clientKey: string;
    now?: number;
    config?: ContactConfig;
    deliver?: (mail: OutboundMail) => Promise<boolean>;
  },
): Promise<ContactResult> {
  const fail = (status: number, message = contactFailure): ContactResult => ({
    status,
    body: { message },
    delivered: false,
  });
  let payload = input;
  if (typeof input === "string") {
    if (input.length > 12_000) return fail(413, "Enter a shorter message.");
    try {
      payload = JSON.parse(input) as unknown;
    } catch {
      return fail(400, "We couldn't read that message. Please try again.");
    }
  }
  if (!payload || typeof payload !== "object") return fail(400, "We couldn't read that message. Please try again.");
  const raw = payload as Record<string, unknown>;
  if (!allowContact(options.clientKey || "local", options.now)) {
    return fail(429, "Please wait a moment and try again.");
  }
  if (typeof raw.company === "string" && raw.company.trim()) {
    return { status: 200, body: { message: contactCategories[0].success }, delivered: false };
  }

  const name = line(raw.name, limits.name);
  if (!name) return fail(400, typeof raw.name === "string" && raw.name.trim().length > limits.name ? "Enter a shorter name." : "Enter your name.");
  const email = emailAddress(raw.email);
  if (!email) return fail(400, "Enter a valid email address.");
  const category = contactCategory(typeof raw.category === "string" ? raw.category : "");
  if (!category) return fail(400, "Choose a category.");
  const subject = line(raw.subject, limits.subject);
  if (!subject) {
    return fail(400, typeof raw.subject === "string" && raw.subject.trim().length > limits.subject ? "Enter a shorter subject." : "Enter a subject.");
  }
  const message = messageText(raw.message);
  if ("error" in message) return fail(400, message.error);

  const version = category.id === "bug" ? optionalDetail(raw.version) : "";
  const os = category.id === "bug" ? optionalDetail(raw.os) : "";
  const mail: OutboundMail = {
    subject: category.subject(subject),
    replyTo: email,
    text: mailBody({
      name,
      email,
      category: category.label,
      subject,
      message: message.text,
      version,
      os,
    }),
  };

  const config = options.config ?? readContactConfig();
  if (contactTransport(config) === "unconfigured") return fail(503);
  try {
    const delivered = options.deliver ? await options.deliver(mail) : await defaultDeliver(config, mail);
    if (!delivered) return fail(502);
    return { status: 200, body: { message: category.success }, delivered: true };
  } catch {
    return fail(502);
  }
}

export function categoryIds(): ContactCategoryId[] {
  return contactCategories.map((item) => item.id);
}
