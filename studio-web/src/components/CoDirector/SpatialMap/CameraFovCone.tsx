/**
 * CameraFovCone — semi-transparent field-of-view wedge extending from the lens.
 *
 * Width is determined by fovPreset (narrow < medium < wide). Opacity is stronger
 * when the camera is selected, lighter otherwise. The cone rotates with the
 * camera orientation.
 */

import { orientationToYaw } from "./gridGeometry";

const FOV_ANGLES: Record<string, number> = {
  narrow: 20,
  medium: 45,
  wide: 75,
};

type Props = {
  orientation: string;
  fovPreset: string;
  radius?: number;
  selected?: boolean;
};

export function CameraFovCone({ orientation, fovPreset, radius = 80, selected = false }: Props) {
  const angle = FOV_ANGLES[fovPreset.toLowerCase()] || FOV_ANGLES.medium;
  const yaw = orientationToYaw(orientation);
  // Convert yaw (0 = North, clockwise) to SVG angle where 0 = East, positive = clockwise.
  // In our geometry 0° yaw points to -y (North). In SVG standard angle 0° is +x (East).
  const svgAngle = (yaw - 90) * (Math.PI / 180);
  const halfAngle = (angle / 2) * (Math.PI / 180);

  const x1 = 0;
  const y1 = 0;
  const x2 = radius * Math.cos(svgAngle - halfAngle);
  const y2 = radius * Math.sin(svgAngle - halfAngle);
  const x3 = radius * Math.cos(svgAngle + halfAngle);
  const y3 = radius * Math.sin(svgAngle + halfAngle);

  const path = `M ${x1} ${y1} L ${x2} ${y2} A ${radius} ${radius} 0 0 1 ${x3} ${y3} Z`;
  const opacity = selected ? 0.45 : 0.25;

  return <path d={path} fill="rgba(14, 165, 233, 0.6)" opacity={opacity} className="spatial-map__fov-cone" />;
}
