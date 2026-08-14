/**
 * CameraMarker — compact SVG production-camera icon with an upright label.
 *
 * The body rotates to face the camera orientation; the label stays upright so
 * C1–C4 is always readable.
 */

import { orientationToYaw } from "./gridGeometry";

type Props = {
  size?: number;
  label: string;
  orientation?: string;
};

export function CameraMarker({ size = 28, label, orientation = "N" }: Props) {
  const w = size;
  const h = size * 0.65;
  const yaw = orientationToYaw(orientation);
  return (
    <g className="spatial-map__camera-body">
      <g transform={`rotate(${yaw})`}>
        <rect
          x={-w / 2}
          y={-h / 2}
          width={w}
          height={h}
          rx={size * 0.12}
          fill="#1f2937"
          stroke="#e2e8f0"
          strokeWidth={1.5}
        />
        <circle cx={0} cy={0} r={size * 0.2} fill="#334155" stroke="#94a3b8" strokeWidth={1} />
        <circle cx={0} cy={0} r={size * 0.1} fill="#0ea5e9" />
        <polygon
          points={`0,${-size * 0.55} ${-size * 0.12},${-size * 0.35} ${size * 0.12},${-size * 0.35}`}
          fill="#f59e0b"
        />
      </g>
      <text
        y={size * 0.55}
        className="spatial-map__camera-label"
        textAnchor="middle"
        dominantBaseline="hanging"
        fontSize={Math.max(9, size * 0.35)}
        fill="#f8fafc"
        fontWeight={700}
      >
        {label}
      </text>
    </g>
  );
}
