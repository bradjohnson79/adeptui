import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";

export type ViewportBookmark = { id: string; label: string; position: number[]; target: number[] };

type Props = {
  glbUrl?: string | null;
  fixture?: boolean;
  onSelect?: (name: string | null) => void;
};

const DEFAULT_BOOKMARKS: ViewportBookmark[] = [
  { id: "hero", label: "Hero", position: [0, 1.6, 4], target: [0, 1.2, 0] },
  { id: "top", label: "Top", position: [0, 8, 0.01], target: [0, 0, 0] },
  { id: "side", label: "Side", position: [5, 1.4, 0], target: [0, 1.2, 0] },
];

export function EnvironmentViewport({ glbUrl, fixture = true, onSelect }: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [bookmarks] = useState(DEFAULT_BOOKMARKS);
  const [selected, setSelected] = useState<string | null>(null);
  const apiRef = useRef<{
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    scene: THREE.Scene;
  } | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1d22);
    const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 500);
    camera.position.set(0, 1.6, 4);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 1.2, 0);

    const grid = new THREE.GridHelper(20, 20, 0x556070, 0x2a3038);
    scene.add(grid);
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(3, 5, 2);
    scene.add(key);

    const transform = new TransformControls(camera, renderer.domElement);
    transform.addEventListener("dragging-changed", (event) => {
      controls.enabled = !event.value;
    });
    scene.add(transform.getHelper());

    // Fixture proxy geometry when no GLB
    const proxy = new THREE.Mesh(
      new THREE.BoxGeometry(2, 1.2, 2),
      new THREE.MeshStandardMaterial({ color: 0x6b7c8a, roughness: 0.35, metalness: 0.05 }),
    );
    proxy.position.y = 0.6;
    proxy.name = fixture ? "fixture-proxy" : "scene-root";
    scene.add(proxy);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const onPointer = (ev: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(scene.children, true);
      const hit = hits.find((h) => h.object instanceof THREE.Mesh && h.object.name);
      if (hit) {
        setSelected(hit.object.name);
        onSelect?.(hit.object.name);
        transform.attach(hit.object);
      }
    };
    renderer.domElement.addEventListener("pointerdown", onPointer);

    let root: THREE.Object3D | null = null;
    if (glbUrl) {
      const loader = new GLTFLoader();
      loader.load(
        glbUrl,
        (gltf) => {
          if (root) scene.remove(root);
          root = gltf.scene;
          root.name = "imported-glb";
          scene.add(root);
          scene.remove(proxy);
        },
        undefined,
        () => {
          // keep fixture proxy; honesty: load failed
        },
      );
    }

    apiRef.current = { camera, controls, scene };

    const resize = () => {
      const w = mount.clientWidth || 640;
      const h = mount.clientHeight || 360;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(mount);

    let raf = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointer);
      transform.dispose();
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      apiRef.current = null;
    };
  }, [glbUrl, fixture, onSelect]);

  const goBookmark = (b: ViewportBookmark) => {
    const api = apiRef.current;
    if (!api) return;
    api.camera.position.fromArray(b.position);
    api.controls.target.fromArray(b.target);
    api.controls.update();
  };

  return (
    <div className="m213-viewport" data-testid="m213-viewport">
      <div className="m213-viewport-toolbar">
        <span>Orbit / Pan / Zoom</span>
        <span>Select + gizmos</span>
        <span>Grid on</span>
        {fixture ? <span className="m213-badge">FIXTURE / PROXY</span> : <span className="m213-badge">GLB</span>}
        {selected ? <span>Selected: {selected}</span> : null}
      </div>
      <div ref={mountRef} className="m213-viewport-canvas" />
      <div className="m213-bookmarks">
        {bookmarks.map((b) => (
          <button key={b.id} type="button" onClick={() => goBookmark(b)}>
            {b.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default EnvironmentViewport;
