import { handleContact } from "../server/contact";

type NodeRequest = {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
  body?: unknown;
  socket?: { remoteAddress?: string };
};

type NodeResponse = {
  statusCode: number;
  setHeader: (name: string, value: string) => void;
  end: (body?: string) => void;
};

function clientKey(req: NodeRequest): string {
  const trust = process.env.CONTACT_TRUST_PROXY === "1";
  const forwarded = req.headers["x-forwarded-for"];
  const raw = Array.isArray(forwarded) ? forwarded[0] : forwarded;
  const forwardedKey = trust ? raw?.split(",")[0]?.trim() : "";
  return forwardedKey || req.socket?.remoteAddress || "local";
}

export default async function handler(req: NodeRequest, res: NodeResponse): Promise<void> {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Allow", "POST");
    res.end(JSON.stringify({ message: "We couldn't send your message right now. Please try again." }));
    return;
  }
  const result = await handleContact(req.body, { clientKey: clientKey(req) });
  res.statusCode = result.status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ message: result.body.message }));
}
