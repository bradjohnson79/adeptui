import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { clearProjectUnlockToken, setProjectUnlockToken } from "../projectSecurity";

function strengthLabel(pw: string): string {
  if (pw.length < 12) return "Too short (min 12)";
  if (pw.length < 16) return "Fair — consider a longer passphrase";
  if (pw.length < 20) return "Good";
  return "Strong passphrase";
}

function PasswordField({
  id,
  label,
  value,
  onChange,
  autoFocus,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoFocus?: boolean;
}) {
  const [show, setShow] = useState(false);
  const [caps, setCaps] = useState(false);
  return (
    <label style={{ display: "block", marginBottom: "0.65rem" }}>
      <span>{label}</span>
      <div style={{ display: "flex", gap: "0.35rem" }}>
        <input
          id={id}
          data-testid={id}
          type={show ? "text" : "password"}
          value={value}
          autoFocus={autoFocus}
          autoComplete="new-password"
          onChange={(e) => onChange(e.target.value)}
          onKeyUp={(e) => setCaps(e.getModifierState?.("CapsLock") || false)}
          style={{ flex: 1 }}
        />
        <button type="button" className="ghost" onClick={() => setShow((s) => !s)} data-testid={`${id}-toggle`}>
          {show ? "Hide" : "Show"}
        </button>
      </div>
      {caps && <span className="muted" style={{ fontSize: "0.8rem" }}>Caps Lock is on</span>}
    </label>
  );
}

export function SetPasswordModal({
  projectId,
  projectName,
  onClose,
  onSaved,
}: {
  projectId: string;
  projectName: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError("");
    if (password.length < 12) {
      setError("Use at least 12 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await api.setProjectPassword(projectId, {
        password,
        confirmPassword: confirm,
        passwordHint: hint,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      data-testid="project-password-setup-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pw-setup-title"
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", zIndex: 1000, overflow: "auto" }}
    >
      <div className="panel" style={{ maxWidth: 420, margin: "10vh auto", padding: "1.25rem" }}>
        <h3 id="pw-setup-title">Password Protect — {projectName}</h3>
        <p className="muted">
          Use a long, memorable passphrase. This password protects access to the project inside Adept UI.
        </p>
        <PasswordField id="project-pw-new" label="New password" value={password} onChange={setPassword} autoFocus />
        <p className="muted" data-testid="project-pw-strength" style={{ fontSize: "0.85rem" }}>
          {strengthLabel(password)}
        </p>
        <PasswordField id="project-pw-confirm" label="Confirm password" value={confirm} onChange={setConfirm} />
        <label style={{ display: "block", marginBottom: "0.65rem" }}>
          Password hint (optional)
          <input
            data-testid="project-pw-hint"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
            maxLength={200}
            style={{ width: "100%" }}
          />
        </label>
        {error && (
          <p className="danger" data-testid="project-pw-setup-error" role="alert">
            {error}
          </p>
        )}
        <div className="row-actions" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <button type="button" className="primary" disabled={busy} data-testid="project-pw-setup-save" onClick={() => void submit()}>
            Save protection
          </button>
          <button type="button" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export function UnlockProjectModal({
  projectId,
  projectName,
  hint,
  onClose,
  onUnlocked,
}: {
  projectId: string;
  projectName: string;
  hint?: string | null;
  onClose: () => void;
  onUnlocked: () => void;
}) {
  const [password, setPassword] = useState("");
  const [rememberFor, setRememberFor] = useState<"session" | "15m" | "1h">("session");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api.unlockProject(projectId, { password, rememberFor });
      if (!r.unlockToken) throw new Error("Unlock did not return a grant token");
      setProjectUnlockToken(projectId, r.unlockToken, r.expiresAt);
      onUnlocked();
      onClose();
    } catch (e) {
      if (e instanceof ApiError && (e.code === "UNLOCK_FAILED" || e.status === 401)) {
        setError("The password is incorrect.");
      } else if (e instanceof ApiError && e.code === "RATE_LIMITED") {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      data-testid="project-unlock-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pw-unlock-title"
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", zIndex: 1000, overflow: "auto" }}
    >
      <div className="panel" style={{ maxWidth: 400, margin: "10vh auto", padding: "1.25rem" }}>
        <h3 id="pw-unlock-title">Unlock Project — {projectName}</h3>
        <p>This project is password protected.</p>
        {hint ? <p className="muted">Hint: {hint}</p> : null}
        <PasswordField id="project-unlock-password" label="Password" value={password} onChange={setPassword} autoFocus />
        <label style={{ display: "block", marginBottom: "0.5rem" }}>
          Remember for
          <select
            data-testid="project-unlock-remember"
            value={rememberFor}
            onChange={(e) => setRememberFor(e.target.value as typeof rememberFor)}
          >
            <option value="session">This session</option>
            <option value="15m">15 minutes</option>
            <option value="1h">1 hour</option>
          </select>
        </label>
        {error && (
          <p className="danger" data-testid="project-unlock-error" role="alert">
            {error}
          </p>
        )}
        <div className="row-actions" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <button
            type="button"
            className="primary"
            disabled={busy}
            data-testid="project-unlock-submit"
            onClick={() => void submit()}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submit();
            }}
          >
            Unlock Project
          </button>
          <button type="button" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>
        <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>
          Forgot project password? Reauthenticate as the Adept UI owner, then use Manage Password Protection → Reset.
        </p>
      </div>
    </div>
  );
}

export function ManagePasswordModal({
  projectId,
  projectName,
  onClose,
  onChanged,
}: {
  projectId: string;
  projectName: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = useState<"status" | "change" | "disable" | "reset">("status");
  const [status, setStatus] = useState<any>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [accountConfirm, setAccountConfirm] = useState("");
  const [disableConfirm, setDisableConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getProjectSecurity(projectId).then(setStatus).catch((e) => setError(e.message));
  }, [projectId]);

  return (
    <div
      className="modal-backdrop"
      data-testid="project-password-manage-modal"
      role="dialog"
      aria-modal="true"
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", zIndex: 1000, overflow: "auto" }}
    >
      <div className="panel" style={{ maxWidth: 460, margin: "8vh auto", padding: "1.25rem" }}>
        <h3>Manage Password Protection — {projectName}</h3>
        <div className="row-actions" style={{ gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
          {(["status", "change", "disable", "reset"] as const).map((t) => (
            <button key={t} type="button" className={tab === t ? "primary" : "ghost"} onClick={() => setTab(t)}>
              {t === "status" ? "View status" : t === "change" ? "Change password" : t === "disable" ? "Disable" : "Reset"}
            </button>
          ))}
        </div>
        {tab === "status" && (
          <div data-testid="project-pw-status">
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>{JSON.stringify(status, null, 2)}</pre>
            <button
              type="button"
              data-testid="project-lock-now"
              onClick={() =>
                void api
                  .lockProjectNow(projectId)
                  .then(() => {
                    clearProjectUnlockToken(projectId);
                    onChanged();
                    onClose();
                  })
                  .catch((e) => setError(e.message))
              }
            >
              Lock now
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="project-temp-unlock"
              onClick={() => setTab("change")}
            >
              Temporarily unlock / change…
            </button>
          </div>
        )}
        {tab === "change" && (
          <div>
            <PasswordField id="project-pw-current" label="Current project password" value={current} onChange={setCurrent} />
            <PasswordField id="project-pw-change-new" label="New password" value={next} onChange={setNext} />
            <PasswordField id="project-pw-change-confirm" label="Confirm new password" value={confirm} onChange={setConfirm} />
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="project-pw-change-save"
              onClick={() => {
                setBusy(true);
                setError("");
                void api
                  .changeProjectPassword(projectId, {
                    currentPassword: current,
                    newPassword: next,
                    confirmPassword: confirm,
                  })
                  .then(() => {
                    clearProjectUnlockToken(projectId);
                    onChanged();
                    onClose();
                  })
                  .catch((e) => setError(e instanceof ApiError && e.code === "UNLOCK_FAILED" ? "The password is incorrect." : e.message))
                  .finally(() => setBusy(false));
              }}
            >
              Change password
            </button>
          </div>
        )}
        {tab === "disable" && (
          <div>
            <PasswordField id="project-pw-disable-current" label="Current password" value={current} onChange={setCurrent} />
            <label>
              <input
                type="checkbox"
                checked={disableConfirm}
                onChange={(e) => setDisableConfirm(e.target.checked)}
                data-testid="project-pw-disable-confirm"
              />{" "}
              Remove password protection
            </label>
            <button
              type="button"
              disabled={busy || !disableConfirm}
              data-testid="project-pw-disable-save"
              onClick={() => {
                setBusy(true);
                void api
                  .disableProjectPassword(projectId, { currentPassword: current, confirm: true })
                  .then(() => {
                    clearProjectUnlockToken(projectId);
                    onChanged();
                    onClose();
                  })
                  .catch((e) => setError(e.message))
                  .finally(() => setBusy(false));
              }}
            >
              Disable protection
            </button>
          </div>
        )}
        {tab === "reset" && (
          <div>
            <p className="muted">Owner reset after Adept UI account reauthentication (local-first: type owner).</p>
            <input
              data-testid="project-pw-reset-account"
              value={accountConfirm}
              onChange={(e) => setAccountConfirm(e.target.value)}
              placeholder="Account confirmation"
              style={{ width: "100%", marginBottom: "0.5rem" }}
            />
            <PasswordField id="project-pw-reset-new" label="New password" value={next} onChange={setNext} />
            <PasswordField id="project-pw-reset-confirm" label="Confirm" value={confirm} onChange={setConfirm} />
            <button
              type="button"
              disabled={busy}
              data-testid="project-pw-reset-save"
              onClick={() => {
                setBusy(true);
                void api
                  .resetProjectPassword(projectId, {
                    accountConfirmation: accountConfirm,
                    newPassword: next,
                    confirmPassword: confirm,
                  })
                  .then(() => {
                    clearProjectUnlockToken(projectId);
                    onChanged();
                    onClose();
                  })
                  .catch((e) => setError(e.message))
                  .finally(() => setBusy(false));
              }}
            >
              Reset protection
            </button>
          </div>
        )}
        {error && (
          <p className="danger" role="alert">
            {error}
          </p>
        )}
        <button type="button" style={{ marginTop: "0.75rem" }} onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
