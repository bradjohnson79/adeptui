import { useState } from "react";
import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorAttachmentTray() {
  const { attachments, removeAttachment } = useCoDirectorSession();
  const [expanded, setExpanded] = useState(false);

  if (!attachments.length) return null;

  const collapsed = attachments.length > 3 && !expanded;
  const visible = collapsed ? attachments.slice(0, 3) : attachments;

  return (
    <div
      className="codirector-attachments"
      aria-label="Attachments"
      data-testid="codirector-attachment-tray"
    >
      <div className="codirector-attachment-grid">
        {visible.map((item) => (
          <div key={item.id} className="codirector-attachment">
            {item.previewUrl ? (
              <img src={item.previewUrl} alt="" />
            ) : (
              <span className="codirector-attachment-icon" aria-hidden>
                {item.kind === "library" ? "Lib" : "File"}
              </span>
            )}
            <div className="codirector-attachment-meta">
              <strong title={item.name}>{item.name}</strong>
              <span>{item.kind === "library" ? "Library asset" : item.mimeType || "File"}</span>
            </div>
            <button
              type="button"
              className="codirector-icon-btn"
              aria-label={`Remove ${item.name}`}
              onClick={() => removeAttachment(item.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      {attachments.length > 3 && (
        <button type="button" className="ghost" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show fewer" : `${attachments.length} assets attached`}
        </button>
      )}
    </div>
  );
}
