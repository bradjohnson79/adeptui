import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { FinalRenderSection, FinalRenderSession } from "../../magiSequence/finalRenderConfirm";

export function MagiFinalRenderDialog({
  summary,
  session,
  busy,
  outputName,
  nameMessage,
  onOutputNameChange,
  onCancel,
  onConfirm,
  onClose,
  onShowViewer,
  onShowLibrary,
  onShowQueue,
}: {
  summary: FinalRenderSection[];
  session: FinalRenderSession;
  busy: boolean;
  outputName: string;
  nameMessage: string | null;
  onOutputNameChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  onClose: () => void;
  onShowViewer: () => void;
  onShowLibrary: () => void;
  onShowQueue: () => void;
}) {
  const logRef = useRef<HTMLUListElement | null>(null);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const running = session.phase === "running" || busy;
  const confirmLocked = running || Boolean(nameMessage);
  const percent = session.phase === "done" ? 100 : Math.min(99, Math.max(0, Math.round(session.progress * 100)));
  const title =
    session.phase === "done" ? "Final Render Complete" : session.phase === "failed" ? "Final Render Stopped" : running ? "Final Render" : "Confirm Final Render";

  useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [session.log]);

  useEffect(() => {
    if (session.phase !== "confirm") return;
    nameRef.current?.focus();
    nameRef.current?.select();
  }, [session.phase]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || running) return;
      if (session.phase === "confirm") onCancel();
      else onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, onClose, running, session.phase]);

  return createPortal(
    <div className="magi-final-render" role="presentation" data-testid="magi-final-render-modal">
      <button
        type="button"
        className="magi-final-render__backdrop"
        aria-label={running ? "Final render in progress" : "Close"}
        onClick={() => {
          if (running) return;
          if (session.phase === "confirm") onCancel();
          else onClose();
        }}
      />
      <div className="magi-final-render__panel" role="dialog" aria-modal="true" aria-labelledby="magi-final-render-title">
        <header className="magi-final-render__head">
          <h2 id="magi-final-render-title">{title}</h2>
          {session.phase === "confirm" ? <p>These are the settings this Final Render will use.</p> : null}
        </header>
        {session.phase === "confirm" ? (
          <div className="magi-final-render__name">
            <label htmlFor="magi-final-render-name">Final Video Name</label>
            <input
              ref={nameRef}
              id="magi-final-render-name"
              type="text"
              data-testid="magi-final-render-name"
              placeholder="Enter final video name"
              value={outputName}
              maxLength={64}
              onChange={(event) => onOutputNameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" || confirmLocked) return;
                event.preventDefault();
                onConfirm();
              }}
            />
            {nameMessage ? (
              <p className="magi-final-render__error" data-testid="magi-final-render-name-error">
                {nameMessage}
              </p>
            ) : (
              <p>This name is used for the library and the video file. You do not need to add .mp4.</p>
            )}
          </div>
        ) : null}
        {session.phase === "confirm" ? (
          <div className="magi-final-render__grid">
            {summary.map((section) => (
              <section key={section.id} data-testid={`magi-final-render-section-${section.id}`}>
                <h3>{section.title}</h3>
                <dl>
                  {section.rows.map((row) => (
                    <div key={row.label}>
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        ) : (
          <div className="magi-final-render__progress" data-testid="magi-final-render-progress">
            <div className="magi-final-render__meter">
              <div
                className="magi-final-render__bar"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
                aria-label="Final render progress"
              >
                <span style={{ width: `${percent}%` }} />
              </div>
              <strong data-testid="magi-final-render-percent">{percent}%</strong>
            </div>
            <p className="magi-final-render__stage" data-testid="magi-final-render-stage">
              {session.phase === "done"
                ? session.outputFile || "Final Render Complete"
                : session.phase === "running" && session.outputName
                  ? `Rendering: ${session.outputName}`
                  : session.message || session.stage || "Working…"}
            </p>
            {session.phase === "running" && session.message ? (
              <p className="magi-final-render__detail" data-testid="magi-final-render-detail">
                {session.message}
              </p>
            ) : null}
            {session.error ? (
              <p className="magi-final-render__error" data-testid="magi-final-render-error">
                {session.error}
              </p>
            ) : null}
            <ul ref={logRef} className="magi-final-render__log" data-testid="magi-final-render-log">
              {session.log.map((note, index) => (
                <li key={`${note.stage}-${note.message}-${index}`} className={note.failed ? "is-failed" : ""}>
                  {note.message}
                </li>
              ))}
            </ul>
          </div>
        )}
        <footer className="magi-final-render__actions">
          {session.phase === "confirm" || running ? (
            <>
              {session.phase === "confirm" ? (
                <button type="button" className="magi-chip" data-testid="magi-final-render-cancel" onClick={onCancel}>
                  Cancel
                </button>
              ) : null}
              <button type="button" className="magi-primary" data-testid="magi-final-render-confirm" disabled={confirmLocked} onClick={onConfirm}>
                Confirm
              </button>
            </>
          ) : null}
          {session.phase === "done" ? (
            <>
              <button type="button" className="magi-chip" data-testid="magi-final-render-viewer" onClick={onShowViewer} disabled={!session.assetId}>
                Show in viewer
              </button>
              <button type="button" className="magi-chip" data-testid="magi-final-render-library" onClick={onShowLibrary} disabled={!session.assetId}>
                Show in Library
              </button>
              <button type="button" className="magi-chip" data-testid="magi-final-render-queue" onClick={onShowQueue}>
                Open render queue
              </button>
              <button type="button" className="magi-primary" data-testid="magi-final-render-close" onClick={onClose}>
                Close
              </button>
            </>
          ) : null}
          {session.phase === "failed" ? (
            <>
              <p className="magi-final-render__error">Close this, then press Final Render when you want to try again.</p>
              <button type="button" className="magi-primary" data-testid="magi-final-render-close" onClick={onClose}>
                Close
              </button>
            </>
          ) : null}
        </footer>
      </div>
    </div>,
    document.body,
  );
}
