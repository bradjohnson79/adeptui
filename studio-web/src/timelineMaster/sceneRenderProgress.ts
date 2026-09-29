import type { BatchBlock, BatchStatus, SceneTimelineMaster } from "./contracts";

/** Creator-facing scene render chrome derived from SceneTimelineMaster (read-only). */

export type SceneGenerationProgress = {
  /** 1-based active batch index (matches BE compute_generation_progress). */
  currentBatchIndex: number;
  totalBatches: number;
  /** QC-eligible complete count (excludes NeedsDialogueRetake). */
  completedBatches?: number;
  /** Render-complete count for overall "K/N batches complete" (includes NeedsDialogueRetake). */
  renderCompletedBatches?: number;
  batchStatus: string;
  /** Fraction 0..1 from BE / jobs. */
  batchProgress: number;
  sceneStatus: string;
  currentBatchId?: string | null;
  message?: string;
  overallBatchesLabel?: string;
  statusLines?: string[];
  phase?: string | null;
  phaseLabel?: string | null;
  progressGrounded?: boolean;
  lastProgressAt?: string | null;
  lastRuntimeEventAt?: string | null;
  elapsedActiveTime?: number | null;
  stalled?: boolean;
  currentNode?: string | null;
  stallLabel?: string | null;
  gpuActive?: boolean | null;
  /** Raw Comfy job message (Sampling step N/M) when the backend forwarded it. */
  comfyMessage?: string | null;
  sceneFinished?: boolean;
  dialogueNeedsRetake?: number;
  dialogueQcLabel?: string | null;
  lifecycleStatus?: string | null;
  sceneFinishedWithAcceptedIssues?: boolean;
};

const ACTIVE_STATUSES = new Set(["Queued", "Generating", "Waiting"]);
const COMPLETE_STATUSES = new Set([
  "CandidateReady",
  "Approved",
  "ApprovedConfigurationChanged",
  "RegenerationRecommended",
]);
/** Render finished for overall counter — includes dialogue retake (media exists). */
const RENDER_COMPLETE_STATUSES = new Set([
  ...COMPLETE_STATUSES,
  "NeedsDialogueRetake",
  "QC_Pending",
  "QC_RetryRequired",
]);

export function sortedBatchBlocks(master: SceneTimelineMaster | null | undefined): BatchBlock[] {
  return [...(master?.batchBlocks || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
}

/** Chip / track-badge labels — keep formatBatchStatus for inspector Approved wording. */
export function batchChipStatus(status: BatchStatus | string): string {
  switch (status) {
    case "Queued":
      return "Queued";
    case "Generating":
    case "Waiting":
      return "Rendering";
    case "Failed":
      return "Failed";
    case "Cancelled":
      return "Cancelled";
    case "CandidateReady":
    case "Approved":
    case "ApprovedConfigurationChanged":
    case "RegenerationRecommended":
      return "Complete";
    case "NeedsDialogueRetake":
      return "Dialogue QC";
    case "QC_Pending":
      return "QC Pending";
    case "QC_RetryRequired":
      return "QC Retry";
    case "Draft":
      return "Draft";
    case "Ready":
      return "Ready";
    default:
      return String(status || "");
  }
}

function batchHasProviderLiveJob(batch: BatchBlock): boolean {
  const batchStatus = String(batch.status || "");
  if (batchStatus === "Cancelled" || batchStatus === "Failed") return false;
  if (String((batch as BatchBlock & { activeJobId?: string | null }).activeJobId || "").trim()) {
    return true;
  }
  return (batch.generationJobs || []).some((job) => {
    const status = String(job.status || "").toLowerCase();
    return status === "running" || status === "submitted" || status === "pending";
  });
}

/** Staged for Generate Scene; waiting on Omni / last-frame / the next slot. */
export function batchAwaitingSequentialSlot(batch: BatchBlock | null | undefined): boolean {
  if (!batch) return false;
  if (String(batch.status || "") !== "Queued") return false;
  if (batchHasProviderLiveJob(batch)) return false;
  return Boolean(String(batch.pendingSnapshotId || "").trim());
}

/** Snapshot staged for this window, and no job has been submitted for it yet.

 * A previous take's finished job must not hide the window. The monitor stays
 * up until that snapshot is actually rendering.
 */
export function batchHasUnsubmittedSnapshot(batch: BatchBlock | null | undefined): boolean {
  if (!batch) return false;
  const status = String(batch.status || "");
  if (
    status === "Generating" ||
    status === "Cancelled" ||
    status === "Failed" ||
    status === "Approved" ||
    status === "CandidateReady" ||
    status === "ApprovedConfigurationChanged"
  ) {
    return false;
  }
  const pending = String(batch.pendingSnapshotId || "").trim();
  if (!pending) return false;
  if (batchHasProviderLiveJob(batch)) return false;
  const submitted = (batch.generationJobs || []).some(
    (job) => String(job.executionSnapshotId || "") === pending,
  );
  return !submitted;
}

export function isSceneRenderActive(master: SceneTimelineMaster | null | undefined): boolean {
  const batches = master?.batchBlocks || [];
  if (batches.some((batch) => String(batch.status || "") === "Generating" || String(batch.status || "") === "Waiting")) {
    return true;
  }
  return batches.some(
    (batch) =>
      batchHasUnsubmittedSnapshot(batch) ||
      (String(batch.status || "") === "Queued" &&
        (batchHasProviderLiveJob(batch) || batchAwaitingSequentialSlot(batch))),
  );
}

function hasPlayableGeneratedTake(batch: BatchBlock): boolean {
  if (String(batch.approvedClip?.assetId || "").trim()) return true;
  return (batch.candidateVersions || []).some((c) => Boolean(String(c.assetId || "").trim()));
}

/** Batches with a playable generated take and a completed/reviewable status. */
export function completedGeneratedBatches(master: SceneTimelineMaster | null | undefined): BatchBlock[] {
  return sortedBatchBlocks(master).filter(
    (batch) => COMPLETE_STATUSES.has(String(batch.status || "")) && hasPlayableGeneratedTake(batch),
  );
}

const COMFY_STEP_RE =
  /(?:sampling step|node(?:\s+progress)?(?:\s+\d+)?)\s+(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)/i;
const BATCH_COUNTER_RE = /batches complete|render batch\s+\d+\s*\/\s*\d+|\bbatch\s+\d+\s*\/\s*\d+/i;
const TRAILING_PCT_RE = /[—-]\s*(\d{1,3})%\s*$/;

/** Integer 0–100 from a Comfy `value/max` message. Ignores batch counters. */
export function comfyProgressPercentFromText(text: string | null | undefined): number | null {
  const raw = String(text || "");
  if (!raw.trim()) return null;
  for (const line of raw.split("\n")) {
    if (BATCH_COUNTER_RE.test(line) && !COMFY_STEP_RE.test(line)) continue;
    const step = COMFY_STEP_RE.exec(line);
    if (!step) continue;
    const value = Number(step[1]);
    const maximum = Number(step[2]);
    if (!Number.isFinite(value) || !Number.isFinite(maximum) || maximum <= 1) continue;
    return Math.max(0, Math.min(100, Math.round((100 * value) / maximum)));
  }
  for (const line of raw.split("\n")) {
    if (/batches complete/i.test(line)) continue;
    const pctMatch = TRAILING_PCT_RE.exec(line.trim());
    if (!pctMatch) continue;
    const pct = Number(pctMatch[1]);
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) continue;
    return pct;
  }
  return null;
}

export function comfyProgressPercentFromJob(
  job:
    | {
        progress?: number | null;
        progress_grounded?: boolean | null;
        progressGrounded?: boolean | null;
        message?: string | null;
      }
    | null
    | undefined,
): number | null {
  if (!job) return null;
  const fromMessage = comfyProgressPercentFromText(job.message);
  if (fromMessage != null) return fromMessage;
  const grounded = job.progress_grounded === true || job.progressGrounded === true;
  if (!grounded || job.progress == null || !Number.isFinite(Number(job.progress))) return null;
  const raw = Number(job.progress);
  const pct = raw <= 1 ? Math.round(raw * 100) : Math.round(raw);
  return Math.max(0, Math.min(100, pct));
}

export function appendComfyPercentLine(status: string, pct: number): string {
  const lines = String(status || "").split("\n");
  if (!lines[0]) return status;
  if (new RegExp(`\\b${pct}%\\b`).test(status)) return status;
  lines[0] = `${lines[0]} — ${pct}%`;
  return lines.join("\n");
}

/** Latest job progress as 0–100, or null when unknown (never invent %). */
export function batchJobProgressPercent(batch: BatchBlock | null | undefined): number | null {
  const jobs = batch?.generationJobs || [];
  if (!jobs.length) return null;
  const latest = jobs[jobs.length - 1];
  if (latest == null) return null;
  const fromMessage = comfyProgressPercentFromText(
    (latest as { message?: string | null }).message,
  );
  if (fromMessage != null) return fromMessage;
  if (latest.progress == null || !Number.isFinite(Number(latest.progress))) return null;
  if (latest.progressGrounded === false) return null;
  const raw = Number(latest.progress);
  if (raw < 0) return null;
  if (raw === 0 && latest.progressGrounded !== true) return null;
  // Contracts: job progress is 0..1; tolerate accidental 0..100.
  const pct = raw <= 1 ? Math.round(raw * 100) : Math.round(raw);
  return Math.max(0, Math.min(100, pct));
}

const PHASE_ACTIVITY: Record<string, string> = {
  queued: "Queued",
  preparing_model: "Preparing model",
  loading_references: "Loading references",
  encoding_prompt: "Encoding prompt",
  sampling: "Sampling",
  decoding: "Decoding",
  finalizing: "Finalizing",
  stalled: "Generation may be stalled",
};

export function formatElapsedClock(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatLastActivity(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const stamp = Date.parse(iso);
  if (!Number.isFinite(stamp)) return "unknown";
  const sec = Math.max(0, (Date.now() - stamp) / 1000);
  if (sec < 60) {
    const n = Math.max(1, Math.round(sec));
    return `${n} second${n === 1 ? "" : "s"} ago`;
  }
  const minutes = Math.max(1, Math.round(sec / 60));
  return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
}

function activityLabel(gp: SceneGenerationProgress | null | undefined): string {
  const phase = String(gp?.phase || "").trim();
  if (phase && PHASE_ACTIVITY[phase]) return PHASE_ACTIVITY[phase];
  const label = String(gp?.phaseLabel || "").trim();
  if (label && label.toLowerCase() !== "generating") return label;
  return "";
}

function sceneVerb(gp: SceneGenerationProgress | null | undefined): string {
  const status = String(gp?.sceneStatus || "").trim().toLowerCase();
  const phase = String(gp?.phase || "").trim();
  if (phase === "preparing") return "Preparing";
  if ((status === "queued" || status === "pending") && (!phase || phase === "queued")) return "Queued";
  if (status === "waiting" && (!phase || phase === "queued")) return "Preparing";
  if (phase === "queued") return "Queued";
  if (phase === "preparing_model" || phase === "loading_references" || phase === "encoding_prompt") {
    return "Preparing";
  }
  if (status === "queued" || status === "pending") return "Queued";
  if (status === "waiting") return "Preparing";
  return "Generating";
}

function isHeartbeatChrome(line: string): boolean {
  return (
    /^Elapsed:/i.test(line) ||
    /^Runtime active/i.test(line) ||
    /^GPU active/i.test(line) ||
    /^Last runtime event:/i.test(line) ||
    /^Last activity:/i.test(line) ||
    /^Generation may be stalled/i.test(line)
  );
}

function buildLiveHeadline(
  gp: SceneGenerationProgress,
  fallbackLine: string,
  batchIndex: number,
  totalBatches: number,
): string {
  const n = Math.min(totalBatches, Math.max(1, Math.floor(Number(gp.currentBatchIndex) || batchIndex || 1)));
  const m = Math.max(1, totalBatches);
  const verb = sceneVerb(gp);
  const activity = activityLabel(gp);
  const parts = [`Render Batch ${n}/${m}`, verb];
  if (activity && activity !== verb) parts.push(activity);
  let line = fallbackLine.startsWith("Render Batch ") || !fallbackLine ? parts.join(" — ") : fallbackLine;
  if (fallbackLine.startsWith("Render Batch ") || !fallbackLine) {
    line = parts.join(" — ");
  }
  const pct = progressPercentFromMasterField(gp);
  if (pct != null && !new RegExp(`\\b${pct}%\\b`).test(line)) {
    line = `${line} — ${pct}%`;
  }
  return stripMisleadingZeroPercent(line);
}

function appendHeartbeatBlock(lines: string[], gp: SceneGenerationProgress | null): string[] {
  const out = lines.filter((ln) => ln && !isHeartbeatChrome(ln));
  if (!gp) return out;
  if (gp.elapsedActiveTime != null && Number.isFinite(Number(gp.elapsedActiveTime))) {
    out.push(`Elapsed: ${formatElapsedClock(gp.elapsedActiveTime)}`);
  }
  if (gp.stalled) {
    out.push("Generation may be stalled");
  } else if (String(gp.sceneStatus || "").toLowerCase() === "generating" || gp.phase) {
    out.push("Runtime active");
    if (gp.gpuActive === true) out.push("GPU active");
  }
  if (gp.lastRuntimeEventAt) {
    out.push(`Last runtime event: ${formatLastActivity(gp.lastRuntimeEventAt)}`);
  }
  return out;
}

function stripMisleadingZeroPercent(line: string): string {
  return String(line || "").replace(/\s[—-]\s*0%\s*$/g, "").trim();
}

function appendStallLines(text: string, gp: SceneGenerationProgress | null): string {
  if (!gp?.stalled) return text;
  if (/Generation may be stalled/i.test(text)) return text;
  const ago = formatLastActivity(gp.lastRuntimeEventAt);
  return `${text}\nGeneration may be stalled\nLast activity: ${ago}`;
}

function withPhaseInsteadOfBareInProgress(line: string, gp: SceneGenerationProgress | null): string {
  const phase = String(gp?.phaseLabel || "").trim();
  if (!phase) return line;
  return line.replace(/—\s*In Progress\b/g, `— ${phase}`);
}

function progressPercentFromMasterField(
  gp: SceneGenerationProgress,
): number | null {
  const fromText = comfyProgressPercentFromText(
    [gp.comfyMessage, gp.message, ...(gp.statusLines || [])].filter(Boolean).join("\n"),
  );
  if (fromText != null) return fromText;
  if (gp.progressGrounded !== true) return null;
  if (gp.batchProgress == null || !Number.isFinite(Number(gp.batchProgress))) return null;
  const raw = Number(gp.batchProgress);
  if (raw < 0) return null;
  const pct = raw <= 1 ? Math.round(raw * 100) : Math.round(raw);
  return Math.max(0, Math.min(100, pct));
}

function resolveActiveBatch(batches: BatchBlock[]): {
  n: number;
  batch: BatchBlock | null;
} {
  const M = batches.length;
  if (!M) return { n: 0, batch: null };
  const genIdx = batches.findIndex((b) => b.status === "Generating");
  if (genIdx >= 0) return { n: genIdx + 1, batch: batches[genIdx] };
  const queuedIdx = batches.findIndex((b) => b.status === "Queued");
  if (queuedIdx >= 0) return { n: queuedIdx + 1, batch: batches[queuedIdx] };
  const waitingIdx = batches.findIndex((b) => String(b.status) === "Waiting");
  if (waitingIdx >= 0) return { n: waitingIdx + 1, batch: batches[waitingIdx] };
  const stagedIdx = batches.findIndex((b) => batchHasUnsubmittedSnapshot(b));
  if (stagedIdx >= 0) return { n: stagedIdx + 1, batch: batches[stagedIdx] };
  const completed = batches.filter((b) => COMPLETE_STATUSES.has(String(b.status || ""))).length;
  const n = Math.min(M, Math.max(1, completed + 1));
  return { n, batch: batches[n - 1] || null };
}

function readGenerationProgress(
  master: SceneTimelineMaster,
): SceneGenerationProgress | null {
  const raw = (master as SceneTimelineMaster & { generationProgress?: SceneGenerationProgress | null })
    .generationProgress;
  if (!raw || typeof raw !== "object") return null;
  if (!Number.isFinite(Number(raw.totalBatches)) || Number(raw.totalBatches) <= 0) return null;
  return raw;
}


function readLifecycleStatus(master: SceneTimelineMaster): string | null {
  const gp = readGenerationProgress(master);
  const fromGp = gp?.lifecycleStatus ? String(gp.lifecycleStatus) : "";
  if (fromGp) return fromGp;
  const sfc = (master as SceneTimelineMaster & { sceneFinalCheck?: { lifecycleStatus?: string } | null })
    .sceneFinalCheck;
  const fromSfc = sfc?.lifecycleStatus ? String(sfc.lifecycleStatus) : "";
  return fromSfc || null;
}

/** Overlay-active lifecycle for Preview Monitor generate HUD (render + stitch only).
 * Final Check / Repairing / Re-verifying are Advanced-drawer stats — not monitor chrome.
 */
const OVERLAY_ACTIVE_LIFECYCLES = new Set([
  "RENDERING",
  "STITCHING",
]);

const FINISHED_LIFECYCLES = new Set([
  "SCENE_FINISHED",
  "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
]);

function hasActiveGenerationJobs(master: SceneTimelineMaster | null | undefined): boolean {
  if (isSceneRenderActive(master)) return true;
  for (const batch of master?.batchBlocks || []) {
    if (batchHasProviderLiveJob(batch)) return true;
  }
  return false;
}

/**
 * LAW: GENERATE SCENE · Multi-batch overlay only while actively rendering or stitching.
 * Final Check / Repairing / Re-verifying belong in Advanced drawer stats — not Preview Monitor.
 * Idle / Ready / finished lifecycle with no active jobs → hide.
 */
export function isSceneGenerationOverlayActive(master: SceneTimelineMaster | null | undefined): boolean {
  if (!master) return false;
  if (isSceneRenderActive(master)) return true;
  if (hasActiveGenerationJobs(master)) return true;
  const life = readLifecycleStatus(master);
  if (!life) return false;
  // Stale/false RENDERING (Draft/Ready idle) must NOT drive overlay — only real
  // active queue (checked above) counts as rendering chrome.
  if (life === "RENDERING") return false;
  if (OVERLAY_ACTIVE_LIFECYCLES.has(life)) return true;
  return false;
}


function renderCompletedCount(batches: BatchBlock[]): number {
  return batches.filter(
    (b) =>
      RENDER_COMPLETE_STATUSES.has(String(b.status || "")) && !batchHasUnsubmittedSnapshot(b),
  ).length;
}

/** Prefer the higher of the server line and the windows already on this master. */
function applyLiveBatchCount(lines: string[], batches: BatchBlock[], total: number): string[] {
  const fromBatches = renderCompletedCount(batches);
  const stated = lines.reduce((max, line) => {
    const match = line.match(/(\d+)\s*\/\s*\d+\s+batches complete/i);
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  const count = Math.max(fromBatches, stated);
  const rest = lines.filter((line) => !/batches complete/i.test(line));
  if (total > 1 || count > 0) rest.push(`${count}/${total} batches complete`);
  return rest;
}

function batchQcRef(batch: BatchBlock): Record<string, unknown> | null {
  for (const ref of batch.references || []) {
    if (ref && typeof ref === "object" && (ref as { kind?: string }).kind === "dialogueQcDiagnostics") {
      return ref as Record<string, unknown>;
    }
  }
  return null;
}

function dialogueQcStatusLines(
  batches: BatchBlock[],
  renderCompleted: number,
  total: number,
  queueActive: boolean,
  repairingActive: boolean = false,
): string[] {
  if (total <= 0) return [];
  const lines: string[] = [];
  const retakeIdxs: number[] = [];
  let qcPass = 0;
  let qcFail = 0;
  let qcPresent = 0;
  let lockedScriptBatches = 0;

  batches.forEach((batch, i) => {
    const status = String(batch.status || "");
    const qc = batchQcRef(batch);
    if (qc) {
      qcPresent += 1;
      const verdict = String(qc.verdict || "").toUpperCase();
      if (verdict === "PASS" && qc.sceneFinishedEligible !== false) qcPass += 1;
      else if (verdict === "FAIL" || verdict === "UNCERTAIN" || qc.sceneFinishedEligible === false) qcFail += 1;
    }
    if (status === "NeedsDialogueRetake") {
      retakeIdxs.push(i + 1);
      if (!qc) qcFail += 1;
    }
    // QC_Pending / QC_RetryRequired = Omni infra — never map to dialogue retake indexes.
    if (qc || status === "NeedsDialogueRetake" || status === "QC_Pending" || status === "QC_RetryRequired") {
      lockedScriptBatches += 1;
    } else {
      const hasManifest = (batch.references || []).some(
        (r) =>
          r &&
          typeof r === "object" &&
          ["dialogueAuthorityManifest", "dialogueRetakeRepair"].includes(
            String((r as { kind?: string }).kind || ""),
          ),
      );
      if (hasManifest) lockedScriptBatches += 1;
    }
  });

  const terminal = batches.filter((b) =>
    RENDER_COMPLETE_STATUSES.has(String(b.status || "")) ||
    ["Failed", "Cancelled"].includes(String(b.status || "")),
  ).length;
  const allGenDone = terminal >= total && !queueActive;
  if (!allGenDone) return lines;

  if (retakeIdxs.length || qcFail > 0) {
    lines.push("Dialogue QC — Failed");
    lines.push("Scene Not Finished");
    // Only claim Repairing when a repair cycle is actually active — never leave
    // stale "Repairing Batch K…" on idle / keep_current finished scenes.
    if (repairingActive) {
      lines.push(`Repairing Batch ${retakeIdxs[0] || 1}…`);
    }
    return lines;
  }

  if (
    lockedScriptBatches > 0 &&
    qcPresent < lockedScriptBatches &&
    qcFail === 0 &&
    qcPass < lockedScriptBatches
  ) {
    lines.push("Dialogue QC — Checking…");
    return lines;
  }

  if (lockedScriptBatches > 0 && qcPass >= lockedScriptBatches && qcFail === 0) {
    lines.push("Dialogue QC — Passed");
    lines.push("Scene Finished");
    return lines;
  }

  // No dialogue gate: never invent Scene Finished from N/N alone.
  void renderCompleted;
  return lines;
}

/**
 * Creator-facing multi-batch status (may be multi-line).
 * Always shows BOTH current batch + overall K/N for multi-batch active renders.
 * Prefers master.generationProgress.statusLines when present.
 * Never invents Scene Finished from N/N alone.
 */
export function formatSceneRenderStatus(master: SceneTimelineMaster | null | undefined): string | null {
  if (!master) return null;
  const batches = sortedBatchBlocks(master);
  const M = batches.length;
  if (!M) return null;

  const life = readLifecycleStatus(master);
  const overlayActive = isSceneGenerationOverlayActive(master);

  // Stale-heal: finished lifecycle + no active work → never surface statusLines.
  if (life && FINISHED_LIFECYCLES.has(life) && !overlayActive) {
    return null;
  }
  if (!overlayActive) {
    return null;
  }

  const gp = readGenerationProgress(master);
  // Explicit ignore: idle/draft sceneStatus or "— idle" statusLines must never surface.
  const sceneStatusRaw = String(gp?.sceneStatus || "").toLowerCase();
  if (
    (sceneStatusRaw === "idle" || sceneStatusRaw === "draft") &&
    !isSceneRenderActive(master) &&
    !hasActiveGenerationJobs(master) &&
    life !== "REPAIRING" &&
    life !== "FINAL_CHECK" &&
    life !== "REVERIFYING" &&
    life !== "STITCHING"
  ) {
    return null;
  }
  // Final Check / Re-verifying are Advanced-only — never Preview Monitor chrome.
  if (life === "FINAL_CHECK" || life === "REVERIFYING") {
    return null;
  }
  if (life === "STITCHING") {
    return "Stitching…";
  }

  // Prefer BE statusLines only while overlay is active (ignore stale idle payload).
  if (gp?.statusLines && Array.isArray(gp.statusLines) && gp.statusLines.length > 0) {
    const idleLine = /—\s*idle$/i;
    const cleaned = gp.statusLines
      .map((ln) => String(ln || ""))
      .filter((ln) => ln && !idleLine.test(ln));
    if (!cleaned.length) {
      // fall through — idle chrome only
    } else {
    const joined = cleaned.join("\n");
    // Extra guard: drop Repairing / QC-failed chrome when finished lifecycle.
    if (
      life &&
      FINISHED_LIFECYCLES.has(life) &&
      /Repairing Batch|Scene Not Finished|Dialogue QC/i.test(joined)
    ) {
      return null;
    }
    // Drop stale "Repairing…" unless lifecycle is actually REPAIRING.
    if (life !== "REPAIRING" && /Repairing Batch/i.test(joined) && !isSceneRenderActive(master)) {
      // Fall through to derive from batches / lifecycle (Final Check is Advanced-only).
    } else {
      const sanitized = cleaned
        .map((ln) => stripMisleadingZeroPercent(withPhaseInsteadOfBareInProgress(ln, gp)))
        .filter(Boolean);
      const hasLiveTelemetry = Boolean(
        gp &&
          (gp.phase ||
            gp.elapsedActiveTime != null ||
            gp.lastRuntimeEventAt ||
            gp.progressGrounded === true ||
            gp.stalled),
      );
      const total =
        gp?.totalBatches != null && Number(gp.totalBatches) > 0 ? Math.floor(Number(gp.totalBatches)) : M;
      if (!hasLiveTelemetry) {
        return appendStallLines(applyLiveBatchCount(sanitized, batches, total).join("\n"), gp);
      }
      const head = sanitized.find((ln) => ln.startsWith("Render Batch ")) || sanitized[0] || "";
      const rest = sanitized.filter((ln) => ln !== head && !isHeartbeatChrome(ln));
      const rebuilt = buildLiveHeadline(gp, head, Number(gp.currentBatchIndex) || 1, total);
      const withBeat = appendHeartbeatBlock([rebuilt], gp);
      return appendStallLines(
        [...withBeat, ...applyLiveBatchCount(rest, batches, total)].filter(Boolean).join("\n"),
        gp,
      );
    }
    } // cleaned.length
  }

  if (life === "REPAIRING") {
    const retake = batches.findIndex((b) => String(b.status || "") === "NeedsDialogueRetake");
    return `Repairing Batch ${retake >= 0 ? retake + 1 : 1}…`;
  }

  const active = isSceneRenderActive(master);
  const fromBatches = renderCompletedCount(batches);
  const fromServer =
    gp?.renderCompletedBatches != null && Number.isFinite(Number(gp.renderCompletedBatches))
      ? Math.max(0, Math.floor(Number(gp.renderCompletedBatches)))
      : 0;
  const renderCompleted = Math.max(fromBatches, fromServer);
  const total = gp?.totalBatches != null && Number(gp.totalBatches) > 0 ? Math.floor(Number(gp.totalBatches)) : M;
  const overall = total > 1 || renderCompleted > 0 ? `${renderCompleted}/${total} batches complete` : null;

  if (active) {
    const preparingNext = batches.some(
      (batch) => batchAwaitingSequentialSlot(batch) || batchHasUnsubmittedSnapshot(batch),
    );
    if (preparingNext && !batches.some((batch) => String(batch.status || "") === "Generating")) {
      const { n } = resolveActiveBatch(batches);
      const batchN = gp?.currentBatchIndex
        ? Math.min(total, Math.max(1, Math.floor(Number(gp.currentBatchIndex) || 1)))
        : n;
      const line = `Render Batch ${batchN}/${total} — Preparing`;
      const hint = "The next parts of this scene are being prepared.";
      return overall ? `${line}\n${hint}\n${overall}` : `${line}\n${hint}`;
    }
    let currentLine: string;
    if (gp) {
      const n = Math.min(total, Math.max(1, Math.floor(Number(gp.currentBatchIndex) || 1)));
      const hasLiveTelemetry = Boolean(
        gp.phase ||
          gp.elapsedActiveTime != null ||
          gp.lastRuntimeEventAt ||
          gp.progressGrounded === true ||
          gp.stalled ||
          gp.phaseLabel,
      );
      if (hasLiveTelemetry) {
        const head = buildLiveHeadline(gp, "", n, total);
        currentLine = appendStallLines(appendHeartbeatBlock([head], gp).join("\n"), gp);
      } else {
        const pct = progressPercentFromMasterField(gp);
        const verb = String(gp.phaseLabel || "").trim() || "In Progress";
        const base = `Render Batch ${n}/${total} — ${verb}`;
        currentLine = appendStallLines(pct == null ? base : `${base} — ${pct}%`, gp);
      }
    } else {
      const { n, batch } = resolveActiveBatch(batches);
      const pct = batchJobProgressPercent(batch);
      let shown: number | null = pct;
      if (pct == null && batch?.status === "Generating") {
        shown = null;
      }
      const base = `Render Batch ${n}/${M} — In Progress`;
      currentLine = shown == null ? base : `${base} — ${shown}%`;
    }
    if (total > 1 && overall) {
      return `${currentLine}\n${overall}`;
    }
    return currentLine;
  }

  const repairingActive = life === "REPAIRING" || hasActiveGenerationJobs(master);
  const qcLines = dialogueQcStatusLines(batches, renderCompleted, total, false, repairingActive);
  if (total > 1 || renderCompleted > 0) {
    const parts = [overall, ...qcLines].filter(Boolean) as string[];
    return parts.length ? parts.join("\n") : null;
  }

  const anyFailed = batches.some((b) => b.status === "Failed");
  const allComplete = batches.every((b) => COMPLETE_STATUSES.has(String(b.status || "")));
  if (allComplete && !anyFailed && !qcLines.length) {
    // Render complete only — not Scene Finished.
    return overall || `Scene Render Complete ${M}/${M}`;
  }
  if (qcLines.length) {
    return [overall, ...qcLines].filter(Boolean).join("\n");
  }
  return null;
}

/** True only while overlay-active work is in flight (render / repair / Final Check / reverify). */

/**
 * Preview Monitor "Generation Complete" notice — not Final Check chrome.
 * Shown when render work is done (100%) so the creator can dismiss and watch.
 * Final Check details stay in Advanced drawer only.
 */
export function sceneGenerationCompleteNotice(
  master: SceneTimelineMaster | null | undefined,
): { percent: number; fingerprint: string } | null {
  if (!master) return null;
  if (isSceneGenerationOverlayActive(master)) return null;
  const batches = sortedBatchBlocks(master);
  if (!batches.length) return null;
  const life = readLifecycleStatus(master);
  if (life === "STITCHING" || life === "RENDERING") return null;
  const postRenderLife = new Set([
    "BATCHES_COMPLETE",
    "FINAL_CHECK",
    "SCENE_NOT_FINISHED",
    "SCENE_FINISHED",
    "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    "REPAIRING",
    "REVERIFYING",
  ]);
  const allComplete = batches.every(
    (b) =>
      COMPLETE_STATUSES.has(String(b.status || "")) ||
      RENDER_COMPLETE_STATUSES.has(String(b.status || "")),
  );
  if (!allComplete && !(life && postRenderLife.has(life))) return null;
  // Lifecycle labels alone are not a finished render. Idle Draft windows can
  // carry SCENE_NOT_FINISHED and must not show Generation Complete.
  const stitchId = String(
    (master as { sceneStitch?: { assetId?: string } | null }).sceneStitch?.assetId || "",
  ).trim();
  if (!stitchId && !batches.some((batch) => hasPlayableGeneratedTake(batch))) return null;
  // A previous take can leave later windows QC_Pending. That is not this take
  // finishing. An open take that still owes a window is not Generation Complete.
  const takeId = String(master.currentSceneTakeId || master.activeSceneTakeId || "");
  const openTake = (master.sceneTakes || []).find((take) => take.id === takeId);
  if (openTake && (openTake.status === "incomplete" || openTake.status === "rendering" || openTake.status === "cancelled")) {
    const members = openTake.batches || [];
    const owesWindow = members.length < batches.length || members.some((member) => !String(member.assetId || "").trim());
    if (owesWindow) return null;
  }
  const gp = readGenerationProgress(master);
  const fingerprint = [
    String(life || ""),
    String(gp?.renderCompletedBatches ?? ""),
    String(gp?.totalBatches ?? batches.length),
    String((master as { currentSceneTakeId?: string | null }).currentSceneTakeId || ""),
    String((master as { sceneStitch?: { assetId?: string } | null }).sceneStitch?.assetId || ""),
  ].join("|");
  return { percent: 100, fingerprint };
}

export function shouldShowSceneRenderStatus(master: SceneTimelineMaster | null | undefined): boolean {
  if (!isSceneGenerationOverlayActive(master)) return false;
  const formatted = formatSceneRenderStatus(master);
  if (!formatted) return false;
  // Belt-and-suspenders: never show idle chrome.
  if (/—\s*idle$/im.test(formatted)) return false;
  return true;
}

/** Shown on the Preview Monitor the instant Generate Scene, Re-Take, or New Take starts. */
export const PREVIEW_GENERATION_STANDBY = "Stand By... Generation Processing.";

/** Live render text wins. Standby covers the gap before the server reports a batch. */
export function previewGenerationNotice(
  master: SceneTimelineMaster | null | undefined,
  generationStandby: boolean,
): string | null {
  if (shouldShowSceneRenderStatus(master)) return formatSceneRenderStatus(master);
  return generationStandby ? PREVIEW_GENERATION_STANDBY : null;
}
