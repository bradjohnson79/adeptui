/**
 * Law 39 — the normal chat is a sentence. Receipts stay behind Technical details.
 */

const INTERNAL = [
  "requested_action",
  "execution_status",
  "toolreceipt",
  "verifiedmutationreceipt",
  "characterid",
  "projectid",
  "workflowid",
  "traceback (most recent call last)",
];

export type CreatorReply = {
  text: string;
  technical: string | null;
};

/** Fields used for stable Co-Director chat identity (not text-only dedupe). */
export type CoDirectorIdentityFields = {
  id?: string | null;
  role: string;
  content?: string | null;
  clientRequestId?: string | null;
  client_request_id?: string | null;
  requestId?: string | null;
  request_id?: string | null;
  messageType?: string | null;
  message_type?: string | null;
  proposalId?: string | null;
  proposal_id?: string | null;
  approvalId?: string | null;
  approval_id?: string | null;
  workflowId?: string | null;
  workflow_id?: string | null;
  workflowSeq?: number | string | null;
  workflow_seq?: number | string | null;
  seq?: number | string | null;
  /** Generation-ready notice identity (not shown in UI). */
  generationReady?: { messageId?: string | null; executionId?: string | null } | null;
};

function looksInternal(text: string): boolean {
  const folded = text.toLowerCase();
  if (INTERNAL.some((marker) => folded.includes(marker))) return true;
  return folded.includes("character.search") && text.includes("->");
}

function layman(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      if (parsed.mutation_status === "proposed") {
        return "This is prepared and awaiting approval. Nothing has been placed or created yet.";
      }
      const message = typeof parsed.message === "string" ? parsed.message.trim() : "";
      if (message && !looksInternal(message)) return message;
      const data = parsed.data as { matches?: Array<{ displayName?: string }> } | undefined;
      const nested = (parsed.evidence as { read?: { result?: { data?: { matches?: Array<{ displayName?: string }> } } } } | undefined)
        ?.read?.result?.data?.matches;
      const matches = data?.matches || nested || [];
      if (matches.length === 1 && matches[0]?.displayName) {
        return `I found ${matches[0].displayName} and I'm using that saved character for the scene.`;
      }
    } catch {
      /* not JSON */
    }
  }
  return "I'll keep going in plain language.";
}

export function projectCreatorReply(content: string): CreatorReply {
  const raw = (content || "").trim();
  if (!raw || !looksInternal(raw)) return { text: raw, technical: null };
  return { text: layman(raw), technical: raw };
}

/** Stable approval-result bubble id shared by HTTP path + conversation projection. */
export function approvalResultMessageId(approvalId: string, outcome: "verified" | "failed" | "result" = "result"): string {
  const id = String(approvalId || "").trim();
  if (!id) return "";
  if (outcome === "verified") return `${id}:verified`;
  if (outcome === "failed") return `${id}:failed`;
  return `${id}:result`;
}

/**
 * Stable identity for Co-Director chat events.
 * Prefer event id, then request+type, proposal/approval result, workflow+seq.
 * Text content is never the primary key.
 */
export function coDirectorMessageIdentity(message: CoDirectorIdentityFields): string {
  const id = String(message.id || "").trim();
  if (id) return `id:${id}`;

  const approvalId = String(message.approvalId || message.approval_id || "").trim();
  if (approvalId) {
    const outcome =
      String(message.messageType || message.message_type || "").trim() === "error" ? "failed" : "result";
    return `approval:${approvalResultMessageId(approvalId, outcome === "failed" ? "failed" : "result")}`;
  }

  const proposalId = String(message.proposalId || message.proposal_id || "").trim();
  if (proposalId) {
    const kind = String(message.messageType || message.message_type || "approval-result").trim() || "approval-result";
    return `proposal:${proposalId}:${kind}`;
  }

  const requestId = String(
    message.clientRequestId ||
      message.client_request_id ||
      message.requestId ||
      message.request_id ||
      "",
  ).trim();
  const role = String(message.role || "").trim() || "assistant";
  const msgType = String(message.messageType || message.message_type || "").trim();
  if (requestId) {
    return msgType ? `request:${requestId}:${role}:${msgType}` : `request:${requestId}:${role}`;
  }

  const workflowId = String(message.workflowId || message.workflow_id || "").trim();
  const seq = message.workflowSeq ?? message.workflow_seq ?? message.seq;
  if (workflowId && seq != null && String(seq).trim() !== "") {
    return `workflow:${workflowId}:seq:${String(seq)}`;
  }
  if (workflowId) {
    return msgType ? `workflow:${workflowId}:${role}:${msgType}` : `workflow:${workflowId}:${role}`;
  }

  return "";
}

function identityKeysFor(message: CoDirectorIdentityFields): string[] {
  const keys = new Set<string>();
  const primary = coDirectorMessageIdentity(message);
  if (primary) keys.add(primary);

  const id = String(message.id || "").trim();
  if (id) {
    keys.add(`id:${id}`);
    // Approval projection ids are "{approvalId}:verified|failed|result".
    if (id.endsWith(":verified") || id.endsWith(":failed") || id.endsWith(":result")) {
      keys.add(`approval:${id}`);
    }
  }

  const genReady = message.generationReady;
  const genMsgId = String((genReady && genReady.messageId) || "").trim();
  const genExecId = String((genReady && genReady.executionId) || "").trim();
  if (genMsgId) keys.add(`id:${genMsgId}`);
  if (genExecId) keys.add(`genrdy:${genExecId}`);
  if (id.startsWith("genrdy:")) keys.add(`genrdy:${id.slice("genrdy:".length)}`);

  const approvalId = String(message.approvalId || message.approval_id || "").trim();
  if (approvalId) {
    const msgType = String(message.messageType || message.message_type || "").trim();
    const outcome =
      msgType === "error" || /couldn.?t approve/i.test(String(message.content || ""))
        ? "failed"
        : id.endsWith(":verified")
          ? "verified"
          : "result";
    keys.add(`approval:${approvalResultMessageId(approvalId, outcome)}`);
    keys.add(`id:${approvalResultMessageId(approvalId, outcome)}`);
  }

  const proposalId = String(message.proposalId || message.proposal_id || "").trim();
  if (proposalId) {
    const kind = String(message.messageType || message.message_type || "approval-result").trim() || "approval-result";
    keys.add(`proposal:${proposalId}:${kind}`);
  }

  const requestId = String(
    message.clientRequestId ||
      message.client_request_id ||
      message.requestId ||
      message.request_id ||
      "",
  ).trim();
  const role = String(message.role || "").trim() || "assistant";
  const msgType = String(message.messageType || message.message_type || "").trim();
  if (requestId) {
    keys.add(msgType ? `request:${requestId}:${role}:${msgType}` : `request:${requestId}:${role}`);
  }

  const workflowId = String(message.workflowId || message.workflow_id || "").trim();
  const seq = message.workflowSeq ?? message.workflow_seq ?? message.seq;
  if (workflowId && seq != null && String(seq).trim() !== "") {
    keys.add(`workflow:${workflowId}:seq:${String(seq)}`);
  }

  return [...keys];
}

/** Insert or replace by stable identity. Same event never appears twice. */
export function upsertCoDirectorMessage<T extends CoDirectorIdentityFields>(
  messages: T[],
  next: T,
): T[] {
  const nextKeys = new Set(identityKeysFor(next).filter(Boolean));
  if (!nextKeys.size) {
    return [...messages, next];
  }
  let replaced = false;
  const out: T[] = [];
  for (const item of messages) {
    const itemKeys = identityKeysFor(item);
    const hit = itemKeys.some((key) => nextKeys.has(key));
    if (hit) {
      if (!replaced) {
        out.push({ ...item, ...next, id: String(next.id || item.id || "") });
        replaced = true;
      }
      continue;
    }
    out.push(item);
  }
  if (!replaced) out.push(next);
  return out;
}

export function mergeServerMessages<T extends CoDirectorIdentityFields & { content: string }>(
  local: T[],
  incoming: T[],
): T[] {
  let merged = [...local];
  const seen = new Set<string>();
  for (const item of merged) {
    for (const key of identityKeysFor(item)) seen.add(key);
  }
  for (const message of incoming) {
    const keys = identityKeysFor(message);
    if (keys.some((key) => seen.has(key))) continue;
    // Legacy fallback only when neither side carries a stable identity.
    if (
      !keys.length &&
      message.role === "assistant" &&
      message.content.trim().length > 0 &&
      merged.some(
        (item) =>
          !coDirectorMessageIdentity(item) &&
          item.role === "assistant" &&
          item.content.trim() === message.content.trim(),
      )
    ) {
      continue;
    }
    merged = upsertCoDirectorMessage(merged, message);
    for (const key of identityKeysFor(message)) seen.add(key);
  }
  return merged;
}
