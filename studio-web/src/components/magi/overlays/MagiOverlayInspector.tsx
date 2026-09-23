import { MagiAccordion } from "../layout/MagiAccordion";
import type { MagiImageElement, MagiOverlayElement, MagiOverlayGroup, MagiTextElement, MagiVectorElement } from "./types";

export function MagiOverlayInspector({
  element,
  accordion,
  setAccordion,
  onChange,
  onChangeId,
  onDelete,
  onDuplicate,
  onBringForward,
  onSendBackward,
  onBringToFront,
  onSendToBack,
  frameRate = 24,
}: {
  element: MagiOverlayElement | null;
  accordion: Record<string, boolean>;
  setAccordion: (id: string, open: boolean) => void;
  onChange: (patch: Partial<MagiOverlayElement>) => void;
  onChangeId?: (id: string, patch: Partial<MagiOverlayElement>) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onBringForward?: () => void;
  onSendBackward?: () => void;
  onBringToFront?: () => void;
  onSendToBack?: () => void;
  frameRate?: number;
}) {
  if (!element) {
    return <p className="magi-muted">Select a title, lower third, shape, or image on the Preview Monitor.</p>;
  }

  const isText = element.type === "text";
  const isVec = element.type === "vector";
  const isGroup = element.type === "group";
  const isImage = element.type === "image";
  const textEl = isText ? (element as MagiTextElement) : null;
  const vecEl = isVec ? (element as MagiVectorElement) : null;
  const groupEl = isGroup ? (element as MagiOverlayGroup) : null;
  const imageEl = isImage ? (element as MagiImageElement) : null;
  const ltTexts = (groupEl?.children || []).filter((c): c is MagiTextElement => c.type === "text");
  const primary = ltTexts[0];
  const secondary = ltTexts[1];
  const fps = Math.max(1, frameRate);
  const startSec = (element.startFrame ?? 0) / fps;
  const endSec = (element.endFrame ?? (element.startFrame ?? 0) + fps * 5) / fps;

  return (
    <div className="magi-overlay-inspector" data-testid="magi-overlay-inspector">
      <div className="magi-row" style={{ gap: 6, marginBottom: 8 }}>
        <button type="button" className="magi-chip" onClick={onDuplicate} aria-label="Duplicate overlay">
          Duplicate
        </button>
        <button type="button" className="magi-chip" onClick={onDelete} aria-label="Delete overlay">
          Delete
        </button>
        <button
          type="button"
          className="magi-chip"
          onClick={() => onChange({ locked: !element.locked })}
          aria-label={element.locked ? "Unlock overlay" : "Lock overlay"}
        >
          {element.locked ? "Unlock" : "Lock"}
        </button>
        <button
          type="button"
          className="magi-chip"
          onClick={() => onChange({ visible: !element.visible })}
          aria-label={element.visible ? "Hide overlay" : "Show overlay"}
        >
          {element.visible ? "Hide" : "Show"}
        </button>
        <button type="button" className="magi-chip" onClick={onBringForward} data-testid="magi-ov-forward">Forward</button>
        <button type="button" className="magi-chip" onClick={onSendBackward} data-testid="magi-ov-back">Back</button>
        <button type="button" className="magi-chip" onClick={onBringToFront} data-testid="magi-ov-front">Front</button>
        <button type="button" className="magi-chip" onClick={onSendToBack} data-testid="magi-ov-behind">Behind</button>
      </div>

      {(isText || isGroup) && (
        <MagiAccordion
          id="overlayText"
          title={isGroup ? "Lower Third" : "Text"}
          open={accordion.overlayText !== false}
          onToggle={(o) => setAccordion("overlayText", o)}
        >
          {textEl ? (
            <>
              <label>
                Content
                <textarea
                  value={textEl.text}
                  rows={3}
                  onChange={(e) => onChange({ text: e.target.value } as Partial<MagiOverlayElement>)}
                />
              </label>
            </>
          ) : groupEl ? (
            <>
              <label>
                Name
                <input
                  value={primary?.text || ""}
                  onChange={(e) => primary && onChangeId?.(primary.id, { text: e.target.value } as Partial<MagiOverlayElement>)}
                />
              </label>
              <label>
                Title
                <input
                  value={secondary?.text || ""}
                  onChange={(e) => secondary && onChangeId?.(secondary.id, { text: e.target.value } as Partial<MagiOverlayElement>)}
                />
              </label>
            </>
          ) : null}
        </MagiAccordion>
      )}

      {textEl && (
        <>
          <MagiAccordion
            id="overlayTypography"
            title="Typography"
            open={!!accordion.overlayTypography}
            onToggle={(o) => setAccordion("overlayTypography", o)}
          >
            <label>
              Font
              <select
                value={textEl.textStyle.fontFamily}
                onChange={(e) =>
                  onChange({
                    textStyle: { ...textEl.textStyle, fontFamily: e.target.value },
                  } as Partial<MagiOverlayElement>)
                }
              >
                <option value="dejavu-sans">DejaVu Sans</option>
                <option value="dejavu-serif">DejaVu Serif</option>
                <option value="inter">Inter</option>
              </select>
            </label>
            <label>
              Size
              <input
                type="number"
                min={4}
                max={600}
                value={textEl.textStyle.fontSize}
                onChange={(e) =>
                  onChange({
                    textStyle: { ...textEl.textStyle, fontSize: Number(e.target.value) },
                  } as Partial<MagiOverlayElement>)
                }
              />
            </label>
            <label>
              Colour
              <input
                type="color"
                value={textEl.textStyle.color}
                onChange={(e) =>
                  onChange({
                    textStyle: { ...textEl.textStyle, color: e.target.value },
                  } as Partial<MagiOverlayElement>)
                }
              />
            </label>
            <label>
              Weight
              <input
                type="number"
                min={100}
                max={900}
                step={100}
                value={textEl.textStyle.fontWeight}
                onChange={(e) =>
                  onChange({
                    textStyle: { ...textEl.textStyle, fontWeight: Number(e.target.value) },
                  } as Partial<MagiOverlayElement>)
                }
              />
            </label>
            <label>
              Align
              <select
                value={textEl.textStyle.alignment}
                onChange={(e) =>
                  onChange({
                    textStyle: {
                      ...textEl.textStyle,
                      alignment: e.target.value as "left" | "center" | "right",
                    },
                  } as Partial<MagiOverlayElement>)
                }
              >
                <option value="left">Left</option>
                <option value="center">Center</option>
                <option value="right">Right</option>
              </select>
            </label>
            <label>
              Letter spacing
              <input
                type="number"
                step={0.1}
                value={textEl.textStyle.letterSpacing}
                onChange={(e) =>
                  onChange({
                    textStyle: { ...textEl.textStyle, letterSpacing: Number(e.target.value) },
                  } as Partial<MagiOverlayElement>)
                }
              />
            </label>
          </MagiAccordion>
          <MagiAccordion
            id="overlayBackground"
            title="Background"
            open={!!accordion.overlayBackground}
            onToggle={(o) => setAccordion("overlayBackground", o)}
          >
            <label>
              <input
                type="checkbox"
                checked={!!textEl.backgroundStyle?.enabled}
                onChange={(e) =>
                  onChange({
                    backgroundStyle: {
                      ...(textEl.backgroundStyle || {
                        enabled: false,
                        fill: "#000000",
                        opacity: 0.55,
                        paddingTop: 8,
                        paddingRight: 14,
                        paddingBottom: 8,
                        paddingLeft: 14,
                        cornerRadius: 4,
                        borderEnabled: false,
                        borderColor: "#fff",
                        borderWidth: 1,
                        autoSize: true,
                        fixedWidth: null,
                      }),
                      enabled: e.target.checked,
                    },
                  } as Partial<MagiOverlayElement>)
                }
              />{" "}
              Enabled
            </label>
            {textEl.backgroundStyle?.enabled ? (
              <>
                <label>
                  Fill
                  <input
                    type="color"
                    value={textEl.backgroundStyle.fill}
                    onChange={(e) =>
                      onChange({
                        backgroundStyle: { ...textEl.backgroundStyle!, fill: e.target.value },
                      } as Partial<MagiOverlayElement>)
                    }
                  />
                </label>
                <label>
                  Opacity
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={textEl.backgroundStyle.opacity}
                    onChange={(e) =>
                      onChange({
                        backgroundStyle: {
                          ...textEl.backgroundStyle!,
                          opacity: Number(e.target.value),
                        },
                      } as Partial<MagiOverlayElement>)
                    }
                  />
                </label>
                <label>
                  Corner radius
                  <input
                    type="number"
                    min={0}
                    max={64}
                    value={textEl.backgroundStyle.cornerRadius}
                    onChange={(e) =>
                      onChange({
                        backgroundStyle: {
                          ...textEl.backgroundStyle!,
                          cornerRadius: Number(e.target.value),
                        },
                      } as Partial<MagiOverlayElement>)
                    }
                  />
                </label>
              </>
            ) : null}
          </MagiAccordion>
        </>
      )}

      {vecEl && (
        <MagiAccordion
          id="overlayShape"
          title="Shape"
          open
          onToggle={() => undefined}
        >
          <label>
            Shape
            <select
              value={vecEl.shape}
              onChange={(e) => onChange({ shape: e.target.value } as Partial<MagiOverlayElement>)}
            >
              {[
                "rectangle",
                "rounded_rectangle",
                "line",
                "circle",
                "ellipse",
                "triangle",
                "chevron",
                "accent_bar",
                "divider",
              ].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Fill
            <input
              type="color"
              value={vecEl.fill || "#7c3aed"}
              onChange={(e) => onChange({ fill: e.target.value } as Partial<MagiOverlayElement>)}
            />
          </label>
          <label>
            Stroke
            <input
              type="color"
              value={vecEl.stroke || "#ffffff"}
              onChange={(e) => onChange({ stroke: e.target.value } as Partial<MagiOverlayElement>)}
            />
          </label>
          <label>
            Stroke width
            <input
              type="number"
              min={0}
              max={40}
              value={vecEl.strokeWidth}
              onChange={(e) => onChange({ strokeWidth: Number(e.target.value) } as Partial<MagiOverlayElement>)}
            />
          </label>
        </MagiAccordion>
      )}

      {imageEl ? (
        <MagiAccordion id="overlayImage" title="Image" open onToggle={() => undefined}>
          <p className="magi-empty">Library image. Transparency is kept.</p>
          <label>
            Fit
            <select
              value={imageEl.fit}
              onChange={(e) => onChange({ fit: e.target.value } as Partial<MagiOverlayElement>)}
            >
              <option value="contain">Contain</option>
              <option value="cover">Cover</option>
            </select>
          </label>
        </MagiAccordion>
      ) : null}

      <MagiAccordion id="overlayTiming" title="Timing" open={accordion.overlayTiming !== false} onToggle={(o) => setAccordion("overlayTiming", o)}>
        <label>
          Start (seconds)
          <input
            type="number"
            min={0}
            step={0.1}
            value={Number(startSec.toFixed(2))}
            onChange={(e) => onChange({ startFrame: Math.max(0, Math.round(Number(e.target.value) * fps)) })}
          />
        </label>
        <label>
          End (seconds)
          <input
            type="number"
            min={0}
            step={0.1}
            value={Number(endSec.toFixed(2))}
            onChange={(e) => onChange({ endFrame: Math.max(1, Math.round(Number(e.target.value) * fps)) })}
          />
        </label>
      </MagiAccordion>

      <MagiAccordion
        id="overlayTransform"
        title="Transform"
        open={accordion.overlayTransform !== false}
        onToggle={(o) => setAccordion("overlayTransform", o)}
      >
        {(["x", "y", "width", "height", "rotation", "opacity"] as const).map((k) => (
          <label key={k}>
            {k}
            <input
              type="number"
              step={k === "opacity" || k === "rotation" ? 0.01 : 0.01}
              value={Number(element[k])}
              onChange={(e) => onChange({ [k]: Number(e.target.value) } as Partial<MagiOverlayElement>)}
            />
          </label>
        ))}
      </MagiAccordion>

      <MagiAccordion
        id="overlayAnimation"
        title="Animation"
        open={!!accordion.overlayAnimation}
        onToggle={(o) => setAccordion("overlayAnimation", o)}
      >
        <p className="magi-empty">Fade is live in Preview and Final Render. Other motions stay Preview-only.</p>
        {textEl || groupEl ? (
          <label>
            Entrance
            <select
              value={(textEl?.animationPreset || groupEl?.animationPreset || "none") as string}
              onChange={(e) =>
                onChange({
                  animationPreset: e.target.value === "none" ? null : e.target.value,
                } as Partial<MagiOverlayElement>)
              }
            >
              {["none", "fade", "slide_left", "slide_right", "slide_up", "slide_down", "scale_in", "wipe"].map(
                (a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                )
              )}
            </select>
          </label>
        ) : null}
      </MagiAccordion>
    </div>
  );
}
