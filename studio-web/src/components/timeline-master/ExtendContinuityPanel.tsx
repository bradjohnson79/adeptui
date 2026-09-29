import { useState } from "react";
import { api } from "../../api";
import type { BatchBlock, ExtendSegment, ReviewCadence, SceneTimelineMaster, TemporalContinuityPacket } from "../../timelineMaster/contracts";
import { HelpTip } from "../HelpTip";

function extendStatusLabel(status: string | undefined) {
  const token = String(status || "").trim();
  if (!token) return "";
  if (token === "Ready") return "Ready";
  if (token === "Failed") return "Failed";
  if (token === "Waiting" || token === "Analyzing") return "Working";
  return token;
}

function continuityChipLabel(status: string | undefined, stale?: boolean) {
  if (stale) return "Needs update";
  if (status === "Failed") return "Match failed";
  if (status === "Waiting" || status === "Analyzing") return "Matching…";
  if (status === "Ready" || status === "Applied") return "Matched";
  return null;
}

export function SceneContinuityPolicy({
  projectId,
  sceneId,
  master,
  selectedBatch,
  onRefresh,
}: {
  projectId: string;
  sceneId: string;
  master: SceneTimelineMaster | null;
  selectedBatch?: BatchBlock | null;
  onRefresh: () => void | Promise<void>;
}) {
  const continuityPolicy = master?.continuityPolicy;
  const isApiContinuity = continuityPolicy?.locality === "api";
  const cdPolicy = master?.coDirectorContinuityPolicy;
  const [cdAdvancedOpen, setCdAdvancedOpen] = useState(false);
  const packets = master?.temporalPackets || [];
  const latestPacket: TemporalContinuityPacket | undefined = selectedBatch
    ? [...packets].reverse().find((packet) => packet.source?.batchId === selectedBatch.id) || packets[packets.length - 1]
    : packets[packets.length - 1];
  const segments = master?.extendSegments || [];
  const latestExtendSegment: ExtendSegment | undefined = segments.length
    ? [...segments].sort((a, b) => (b.continuityRevision || 0) - (a.continuityRevision || 0))[0]
    : undefined;
  const longFormContinuity = master?.longFormContinuity;

  return (
    <>
      <div className="field" data-testid="timeline-cd-continuity">
        <span>
          Co-Director Continuity
          <HelpTip text="When this is on, Adept looks at the finished shot and helps the next generation continue instead of starting over. You do not need to open Co-Director." />
        </span>
        <label className="scene-meta">
          <input
            type="checkbox"
            data-testid="timeline-cd-continuity-enabled"
            checked={cdPolicy?.enabled !== false}
            onChange={(event) => {
              void api
                .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, { enabled: event.target.checked })
                .then(onRefresh);
            }}
          />{" "}
          {cdPolicy?.enabled === false ? "Off" : "On"}
        </label>
        <fieldset className="field" data-testid="timeline-cd-review-cadence">
          <legend>
            Review
            <HelpTip text="Automatic reviews the full approved shot (up to about 15 seconds) so early and mid-shot events carry into the next generation. 3 or 5 seconds reviews only the end of the shot. Every batch also reviews the full shot once it finishes." />
          </legend>
          {(
            [
              ["automatic", "Automatic"],
              ["interval_3", "3 sec"],
              ["interval_5", "5 sec"],
              ["every_batch", "Every batch"],
            ] as Array<[ReviewCadence, string]>
          ).map(([value, label]) => (
            <label key={value} className="scene-meta">
              <input
                type="radio"
                name="timeline-cd-review"
                data-testid={`timeline-cd-cadence-${value}`}
                checked={(cdPolicy?.reviewCadence || "automatic") === value}
                onChange={() => {
                  void api
                    .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, { reviewCadence: value })
                    .then(onRefresh);
                }}
              />{" "}
              {label}
            </label>
          ))}
        </fieldset>
        <label className="field">
          <span>
            Continuity Protection
            <HelpTip text="Strong keeps successful motion and screen geography and finishes unfinished action. Standard is a lighter touch." />
          </span>
          <select
            data-testid="timeline-cd-protection"
            value={cdPolicy?.protection || "strong"}
            onChange={(event) => {
              void api
                .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, { protection: event.target.value })
                .then(onRefresh);
            }}
          >
            <option value="strong">Strong</option>
            <option value="standard">Standard</option>
          </select>
        </label>
        <button
          type="button"
          className="ghost"
          data-testid="timeline-cd-advanced-toggle"
          onClick={() => setCdAdvancedOpen((open) => !open)}
        >
          {cdAdvancedOpen ? "Hide advanced" : "Advanced"}
        </button>
        {cdAdvancedOpen ? (
          <div data-testid="timeline-cd-advanced">
            <label className="field">
              <span>Fast Vision</span>
              <input value={cdPolicy?.fastVisionModel || "VideoChat3"} readOnly />
            </label>
            <label className="field">
              <span>Deep Review</span>
              <select
                data-testid="timeline-cd-deep-review"
                value={cdPolicy?.deepReview || "auto"}
                onChange={(event) => {
                  void api
                    .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, { deepReview: event.target.value })
                    .then(onRefresh);
                }}
              >
                <option value="auto">Automatic</option>
                <option value="off">Off</option>
                <option value="on">On</option>
              </select>
            </label>
            <label className="scene-meta">
              <input
                type="checkbox"
                data-testid="timeline-cd-show-debug"
                checked={Boolean(cdPolicy?.showDebugState)}
                onChange={(event) => {
                  void api
                    .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, {
                      showDebugState: event.target.checked,
                    })
                    .then(onRefresh);
                }}
              />{" "}
              Show review details
            </label>
          </div>
        ) : null}
        {latestPacket?.availability === "unavailable" ? (
          <p className="scene-meta" data-testid="timeline-cd-unavailable">
            Co-Director visual continuity unavailable. Timeline generation may continue without visual review.
          </p>
        ) : null}
        {latestPacket?.creatorMarker ? (
          <p className="scene-meta" data-testid="timeline-cd-marker">
            {latestPacket.creatorMarker}
          </p>
        ) : null}
        {latestPacket && latestPacket.availability !== "unavailable" ? (
          <button
            type="button"
            className="ghost"
            data-testid="timeline-cd-reject"
            onClick={() => {
              void api
                .directorTimelineRejectTemporalContinuation(projectId, sceneId, {
                  packetId: latestPacket.packetId,
                  manualNote: cdPolicy?.creatorNextBatchNote || undefined,
                })
                .then(onRefresh);
            }}
          >
            Don’t use this continuation
          </button>
        ) : null}
        <label className="field">
          <span>
            Note for the next shot
            <HelpTip text="Optional. Tell Adept what the next generation should finish or avoid." />
          </span>
          <textarea
            data-testid="timeline-cd-next-note"
            rows={2}
            defaultValue={cdPolicy?.creatorNextBatchNote || ""}
            onBlur={(event) => {
              const value = event.target.value;
              if (value === (cdPolicy?.creatorNextBatchNote || "")) return;
              void api
                .directorTimelineSetCoDirectorContinuityPolicy(projectId, sceneId, {
                  creatorNextBatchNote: value,
                })
                .then(onRefresh);
            }}
          />
        </label>
        {cdPolicy?.showDebugState && latestPacket ? (
          <p className="scene-meta" data-testid="timeline-cd-debug">
            Review {latestPacket.availability}
            {latestPacket.reason ? ` · ${latestPacket.reason}` : ""}
            {latestPacket.source?.reviewCadence ? ` · ${latestPacket.source.reviewCadence}` : ""}
            {latestPacket.extras?.reviewWindowKind
              ? ` · ${String(latestPacket.extras.reviewWindowKind)}`
              : ""}
          </p>
        ) : null}
      </div>
      <p className="scene-meta">
        Shot matching uses the last moments of the previous shot so the next generation can start from the same picture.
      </p>
      {isApiContinuity ? (
        <label className="field">
          <span>Auto Continuity</span>
          <select
            data-testid="timeline-continuity-window"
            value={String(continuityPolicy?.configuredTailDuration ?? 0)}
            onChange={(event) => {
              const n = Number(event.target.value);
              void api.directorTimelineSetContinuityPolicy(projectId, sceneId, { configuredTailDuration: n }).then(onRefresh);
            }}
          >
            <option value="0">Off</option>
            <option value="3">Last 3 seconds</option>
            <option value="5">Last 5 seconds</option>
          </select>
          <HelpTip text="Off means Adept will not spend API credits to match shots in the background. 3 or 5 seconds uses the end of the previous shot when you generate the next one." />
        </label>
      ) : (
        <p className="scene-meta" data-testid="timeline-continuity-local-lock">
          Auto Continuity is on. Adept uses the last 5 seconds of the previous shot — or the whole shot if it is shorter.
        </p>
      )}
      {(latestExtendSegment || longFormContinuity) && (
        <div className="timeline-inspector__extend-status" data-testid="timeline-extend-status">
          <strong>Next shot</strong>
          {latestExtendSegment ? (
            <p className="scene-meta" data-testid="timeline-extend-segment-status">
              {extendStatusLabel(latestExtendSegment.status)}
              {latestExtendSegment.prompt ? ` · “${latestExtendSegment.prompt}”` : null}
            </p>
          ) : null}
          {longFormContinuity?.storyState ? (
            <p className="scene-meta" data-testid="timeline-extend-story-state">
              {longFormContinuity.stale ? "Scene state needs refresh — " : ""}
              {longFormContinuity.storyState}
            </p>
          ) : null}
        </div>
      )}
    </>
  );
}

export function BatchContinuityBridges({
  projectId,
  sceneId,
  master,
  selectedBatch,
  onRefresh,
}: {
  projectId: string;
  sceneId: string;
  master: SceneTimelineMaster | null;
  selectedBatch: BatchBlock;
  onRefresh: () => void | Promise<void>;
}) {
  const incoming = (master?.continuityBridges || []).find(
    (bridge) => bridge.targetBatchId === selectedBatch.id && bridge.status !== "Superseded",
  );
  return (
    <>
      {selectedBatch.downstreamStale ? (
        <p className="scene-meta" data-testid="timeline-batch-stale">
          This shot still uses the previous take from earlier in the scene.
        </p>
      ) : null}
      {incoming && incoming.status !== "Failed" ? (
        <p className="scene-meta" data-testid="timeline-batch-continuity-status">
          Continuity: {continuityChipLabel(incoming.status) || incoming.status}
        </p>
      ) : null}
      {incoming && incoming.status === "Failed" ? (
        <div data-testid="timeline-batch-continuity-failed">
          <p className="scene-meta">Matching the previous shot failed.</p>
          <button type="button" onClick={() => void api.directorTimelineRetryBridge(projectId, sceneId, incoming.bridgeId).then(onRefresh)}>
            Retry
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => void api.directorTimelineContinueWithoutBridge(projectId, sceneId, incoming.bridgeId).then(onRefresh)}
          >
            Continue without matching
          </button>
        </div>
      ) : null}
    </>
  );
}
