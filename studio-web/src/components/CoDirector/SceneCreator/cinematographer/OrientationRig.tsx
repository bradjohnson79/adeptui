/**
 * Imperative Three.js orientation viewport for Scene Creator.
 * Reuses the EnvironmentViewport pattern (mount + renderer + dispose). No R3F / Babylon.
 */
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { clampPitch, clampRoll, clampZoom, wrapYaw, zoomToLens, type AxisLocks } from "./orientationMath";

export type OrientationValue = {
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
  zoom: number;
};

type Props = {
  active: boolean;
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
  zoom: number;
  targetLock?: boolean;
  axisLocks?: AxisLocks;
  compact?: boolean;
  onChange: (next: OrientationValue) => void;
  onCommit: (next: OrientationValue) => void;
};

const SUBJECT_HEIGHT = 1.2;
const CAMERA_DISTANCE = 3.2;
const YAW_PER_PX = 0.35;
const PITCH_PER_PX = 0.28;
const ROLL_PER_PX = 0.18;
const ZOOM_PER_WHEEL = 0.0018;

function lensToFov(zoom: number): number {
  const lens = zoomToLens(zoom);
  return THREE.MathUtils.radToDeg(2 * Math.atan(36 / (2 * lens)));
}

function applyCinePose(
  cineCam: THREE.PerspectiveCamera,
  helper: THREE.CameraHelper,
  value: OrientationValue,
  targetLock: boolean,
): void {
  const yaw = THREE.MathUtils.degToRad(value.yawDegrees);
  const pitch = THREE.MathUtils.degToRad(value.pitchDegrees);
  const cosPitch = Math.cos(pitch);
  cineCam.position.set(
    CAMERA_DISTANCE * Math.sin(yaw) * cosPitch,
    SUBJECT_HEIGHT + CAMERA_DISTANCE * Math.sin(pitch),
    CAMERA_DISTANCE * Math.cos(yaw) * cosPitch,
  );
  cineCam.fov = lensToFov(value.zoom);
  cineCam.updateProjectionMatrix();
  if (targetLock) {
    cineCam.lookAt(0, SUBJECT_HEIGHT, 0);
  } else {
    cineCam.lookAt(
      cineCam.position.x - Math.sin(yaw),
      SUBJECT_HEIGHT,
      cineCam.position.z - Math.cos(yaw),
    );
  }
  cineCam.rotateZ(THREE.MathUtils.degToRad(value.rollDegrees));
  helper.update();
}

function tintHelper(helper: THREE.CameraHelper, color: number): void {
  helper.traverse((obj) => {
    const line = obj as THREE.LineSegments;
    if (line.material && line.material instanceof THREE.Material) {
      const mat = line.material as THREE.LineBasicMaterial;
      if ("color" in mat) mat.color.set(color);
    }
  });
}

export function OrientationRig({
  active,
  yawDegrees,
  pitchDegrees,
  rollDegrees,
  zoom,
  targetLock = true,
  axisLocks,
  compact = false,
  onChange,
  onCommit,
}: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const liveRef = useRef<OrientationValue>({ yawDegrees, pitchDegrees, rollDegrees, zoom });
  const targetLockRef = useRef(targetLock);
  const locksRef = useRef(axisLocks);
  const onChangeRef = useRef(onChange);
  const onCommitRef = useRef(onCommit);
  const draggingRef = useRef(false);
  const applyRef = useRef<((value: OrientationValue) => void) | null>(null);

  liveRef.current = { yawDegrees, pitchDegrees, rollDegrees, zoom };
  targetLockRef.current = targetLock;
  locksRef.current = axisLocks;
  onChangeRef.current = onChange;
  onCommitRef.current = onCommit;

  useEffect(() => {
    if (!draggingRef.current) {
      applyRef.current?.({ yawDegrees, pitchDegrees, rollDegrees, zoom });
    }
  }, [yawDegrees, pitchDegrees, rollDegrees, zoom, targetLock]);

  useEffect(() => {
    if (!active) return;
    const mount = mountRef.current;
    if (!mount) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setUnavailable(true);
      return;
    }
    if (!renderer.getContext()) {
      renderer.dispose();
      setUnavailable(true);
      return;
    }
    setUnavailable(false);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e1218);

    const viewCam = new THREE.PerspectiveCamera(40, 1, 0.05, 80);
    viewCam.position.set(4.6, 3.1, 5.4);
    viewCam.lookAt(0, 1.0, 0);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x0e1218, 1);
    mount.appendChild(renderer.domElement);
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.touchAction = "none";

    const grid = new THREE.GridHelper(10, 10, 0x2a4a4a, 0x1a2830);
    scene.add(grid);
    scene.add(new THREE.AmbientLight(0xb8d4d0, 0.45));
    const key = new THREE.DirectionalLight(0x7ee0d0, 1.05);
    key.position.set(2.4, 4.2, 3.2);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x2dd4bf, 0.55);
    rim.position.set(-3, 2.2, -2);
    scene.add(rim);

    const holo = new THREE.MeshStandardMaterial({
      color: 0x66e0d0,
      emissive: 0x14524c,
      roughness: 0.28,
      metalness: 0.15,
      transparent: true,
      opacity: 0.38,
    });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 0.95, 6, 12), holo);
    body.position.y = 0.85;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), holo);
    head.position.y = 1.62;
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.CapsuleGeometry(0.28, 0.95, 4, 8)),
      new THREE.LineBasicMaterial({ color: 0x2dd4bf, transparent: true, opacity: 0.85 }),
    );
    edges.position.y = 0.85;
    scene.add(body, head, edges);

    const cineCam = new THREE.PerspectiveCamera(lensToFov(liveRef.current.zoom), 16 / 9, 0.2, 8);
    const helper = new THREE.CameraHelper(cineCam);
    tintHelper(helper, 0x2dd4bf);
    scene.add(cineCam);
    scene.add(helper);

    const apply = (value: OrientationValue) => {
      applyCinePose(cineCam, helper, value, targetLockRef.current);
    };
    applyRef.current = apply;
    apply(liveRef.current);

    const resize = () => {
      const w = mount.clientWidth || 320;
      const h = mount.clientHeight || 220;
      viewCam.aspect = w / h;
      viewCam.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(mount);

    const pointer = { lastX: 0, lastY: 0, shift: false };

    const readLive = (): OrientationValue => ({ ...liveRef.current });

    const nudge = (dx: number, dy: number, shift: boolean) => {
      const locks = locksRef.current || {};
      const current = readLive();
      let next = { ...current };
      if (shift) {
        if (!locks.roll) next.rollDegrees = clampRoll(current.rollDegrees + dx * ROLL_PER_PX);
      } else {
        if (!locks.yaw) next.yawDegrees = wrapYaw(current.yawDegrees + dx * YAW_PER_PX);
        if (!locks.pitch) next.pitchDegrees = clampPitch(current.pitchDegrees - dy * PITCH_PER_PX);
      }
      liveRef.current = next;
      apply(next);
      onChangeRef.current(next);
    };

    const onPointerDown = (ev: PointerEvent) => {
      draggingRef.current = true;
      pointer.lastX = ev.clientX;
      pointer.lastY = ev.clientY;
      pointer.shift = ev.shiftKey;
      renderer.domElement.setPointerCapture(ev.pointerId);
    };
    const onPointerMove = (ev: PointerEvent) => {
      if (!draggingRef.current) return;
      const dx = ev.clientX - pointer.lastX;
      const dy = ev.clientY - pointer.lastY;
      pointer.lastX = ev.clientX;
      pointer.lastY = ev.clientY;
      pointer.shift = ev.shiftKey;
      if (dx === 0 && dy === 0) return;
      nudge(dx, dy, ev.shiftKey);
    };
    const endDrag = (ev: PointerEvent) => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      try {
        renderer.domElement.releasePointerCapture(ev.pointerId);
      } catch {
        /* already released */
      }
      onCommitRef.current({ ...liveRef.current });
    };
    let wheelTimer: number | null = null;
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      if (locksRef.current?.zoom) return;
      const current = readLive();
      const next = {
        ...current,
        zoom: clampZoom(current.zoom - ev.deltaY * ZOOM_PER_WHEEL),
      };
      liveRef.current = next;
      apply(next);
      onChangeRef.current(next);
      if (wheelTimer != null) window.clearTimeout(wheelTimer);
      wheelTimer = window.setTimeout(() => {
        wheelTimer = null;
        onCommitRef.current({ ...liveRef.current });
      }, 120);
    };

    const el = renderer.domElement;
    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener("wheel", onWheel, { passive: false });

    let raf = 0;
    const tick = () => {
      renderer.render(scene, viewCam);
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      if (wheelTimer != null) window.clearTimeout(wheelTimer);
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", endDrag);
      el.removeEventListener("pointercancel", endDrag);
      el.removeEventListener("wheel", onWheel);
      applyRef.current = null;
      draggingRef.current = false;
      helper.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [active]);

  if (!active) return null;

  return (
    <div
      className={compact ? "cine-orient-viewport cine-orient-viewport--compact" : "cine-orient-viewport"}
      data-testid="cine-orient-viewport"
    >
      {unavailable ? <p className="muted cine-orient-unavailable">3D viewport unavailable</p> : null}
      <div ref={mountRef} className="cine-orient-viewport__mount" hidden={unavailable} />
    </div>
  );
}
