/**
 * Center-image mask painter for Scene Creator Inpaint.
 * Controls live in the left accordion; painting happens on the hero image.
 */
import { useState } from "react";
import { ImageMaskEditor } from "../../../imageEdit/ImageMaskEditor";
import { useInpaintSession } from "./inpaintSession";

export function CenterMaskCanvas({
  imageUrl,
  sourceAssetId,
  cameraVersion,
}: {
  imageUrl: string;
  sourceAssetId: string;
  cameraVersion?: number | null;
}) {
  const session = useInpaintSession();
  const [cursor, setCursor] = useState<{ x: number; y: number; on: boolean }>({ x: 0, y: 0, on: false });

  return (
    <div
      className={
        session.maskInteractive
          ? "scene-creator-center-mask is-interactive"
          : "scene-creator-center-mask"
      }
      data-testid="scene-creator-center-mask"
      onPointerMove={(event) => {
        if (!session.maskInteractive) return;
        const rect = event.currentTarget.getBoundingClientRect();
        setCursor({ x: event.clientX - rect.left, y: event.clientY - rect.top, on: true });
      }}
      onPointerLeave={() => setCursor((prev) => ({ ...prev, on: false }))}
    >
      <ImageMaskEditor
        ref={session.maskRef}
        imageUrl={imageUrl}
        hideChrome
        fill
        tool={session.tool}
        brushSize={session.brushSize}
        overlayOpacity={session.accordionOpen ? 0.45 : 0}
        interactive={session.maskInteractive}
        onChange={(next) => {
          session.setHasMask(next);
          if (next) {
            session.setMaskSourceAssetId(sourceAssetId);
            session.setMaskCameraVersion(cameraVersion ?? null);
          }
        }}
      />
      {session.maskInteractive && cursor.on ? (
        <span
          className="scene-creator-center-mask__cursor"
          style={{
            width: session.brushSize,
            height: session.brushSize,
            left: cursor.x,
            top: cursor.y,
          }}
        />
      ) : null}
    </div>
  );
}
