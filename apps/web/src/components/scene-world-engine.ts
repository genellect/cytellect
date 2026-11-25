import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/** The landing page's 3D world, after Lusion's dark hero: a pile of glossy six-armed hollow crosses in white,
 *  black and blue, lit by a soft studio room on a dark slate ground. They hold together as one loose cluster,
 *  shoulder each other aside, give way to the pointer and tumble as the page scrolls past them. The canvas is
 *  fixed behind every section. Physics is a small hand-written spring model (no engine): a pull towards the
 *  cluster's anchor, pairwise pushes between bounding spheres, and a push away from the pointer. */
export type SceneWorld = {
  /** Page progress, 0 at the top and 1 at the bottom. */
  progress(value: number): void;
  pointer(x: number, y: number, inside: boolean): void;
  running(value: boolean): void;
  dispose(): void;
};
type Options = { still: boolean; compact: boolean };

/** One hollow arm: a thick tube with a bored end and softened rims, turned on a lathe. */
function arm() {
  const outer = 0.34, inner = 0.15, half = 1.0, bevel = 0.05;
  const profile = [
    [inner, -half + bevel], [inner, half - bevel], [inner + bevel, half], [outer - bevel, half], [outer, half - bevel],
    [outer, -half + bevel], [outer - bevel, -half], [inner + bevel, -half], [inner, -half + bevel],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  return new THREE.LatheGeometry(profile, 40);
}

function cross() {
  const y = arm(), x = arm().rotateZ(Math.PI / 2), z = arm().rotateX(Math.PI / 2);
  const merged = mergeGeometries([y, x, z], false)!;
  [y, x, z].forEach(part => part.dispose());
  merged.computeBoundingSphere();
  return merged;
}

/** The anchor of the cluster down the page, in page-progress order: it keeps to the open side of each section. */
const ANCHORS: { at: number; p: [number, number, number]; spread: number }[] = [
  { at: 0.0, p: [9, 0, -1], spread: 1 },
  { at: 0.12, p: [9.5, -2.2, -2], spread: 1 },
  { at: 0.3, p: [9.5, 1.4, -2], spread: 0.95 },
  { at: 0.5, p: [-9.5, -0.5, -2], spread: 1 },
  { at: 0.68, p: [9.5, 0.6, -2], spread: 1 },
  { at: 0.84, p: [9.5, -1.2, -1.5], spread: 1 },
  { at: 1.0, p: [0, -6.5, -3], spread: 1.25 },
];

export function mountSceneWorld(host: HTMLElement, options: Options): SceneWorld | null {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: options.compact ? "low-power" : "high-performance" });
  } catch {
    return null;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, options.compact ? 1.5 : 2));
  // Neutral tone mapping keeps the blue saturated and the white white, as in the reference.
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14151b);
  scene.fog = new THREE.Fog(0x14151b, 16, 34);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = pmrem.fromScene(new RoomEnvironment(), 0.03).texture;
  scene.environment = room;
  const key = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.set(-4, 6, 8);
  scene.add(key);

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 80);
  camera.position.set(0, 0, 18);

  const geometry = cross();
  const materials = [
    new THREE.MeshPhysicalMaterial({ color: 0xd9d9de, roughness: 0.22, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.12 }),
    new THREE.MeshPhysicalMaterial({ color: 0x0a0a0c, roughness: 0.16, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.06 }),
    new THREE.MeshPhysicalMaterial({ color: 0x1a20d8, roughness: 0.34, metalness: 0, clearcoat: 0.6, clearcoatRoughness: 0.3 }),
  ];
  const count = options.compact ? 12 : 18;
  const size = 1.7, radius = 1.06 * size;
  // A fixed seed, so the pile has the same shape on every visit.
  let seed = 7;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  type Body = { mesh: THREE.Mesh; v: THREE.Vector3; w: THREE.Vector3; home: THREE.Vector3 };
  const bodies: Body[] = Array.from({ length: count }, (_, index) => {
    const mesh = new THREE.Mesh(geometry, materials[index % 5 < 2 ? 0 : index % 5 < 4 ? 1 : 2]);
    mesh.scale.setScalar(size);
    const home = new THREE.Vector3((random() - 0.5) * 7, (random() - 0.5) * 9, (random() - 0.5) * 5);
    mesh.position.copy(home);
    mesh.rotation.set(random() * Math.PI, random() * Math.PI, random() * Math.PI);
    scene.add(mesh);
    return { mesh, v: new THREE.Vector3(), w: new THREE.Vector3((random() - 0.5) * 0.3, (random() - 0.5) * 0.3, (random() - 0.5) * 0.3), home };
  });

  const anchorAt = (p: number, out: THREE.Vector3) => {
    const i = Math.max(0, ANCHORS.findIndex((stop, k) => k < ANCHORS.length - 1 && p <= ANCHORS[k + 1].at));
    const a = ANCHORS[i], b = ANCHORS[Math.min(i + 1, ANCHORS.length - 1)];
    const t = b.at > a.at ? Math.min(1, Math.max(0, (p - a.at) / (b.at - a.at))) : 0;
    const s = t * t * (3 - 2 * t);
    out.set(a.p[0] + (b.p[0] - a.p[0]) * s, a.p[1] + (b.p[1] - a.p[1]) * s, a.p[2] + (b.p[2] - a.p[2]) * s);
    return a.spread + (b.spread - a.spread) * s;
  };

  let target = 0, shown = 0, presence = 0, active = true, frame = 0, last = performance.now();
  const pointerNdc = new THREE.Vector2(0, 0), ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const pointerWorld = new THREE.Vector3(), anchor = new THREE.Vector3(), toward = new THREE.Vector3(), delta = new THREE.Vector3();
  let lastShown = 0;

  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(1, height);
    // On narrow screens the camera steps back, so the pile still reads as a pile beside the copy.
    camera.position.z = camera.aspect < 0.8 ? 30 : 18;
    camera.updateProjectionMatrix();
  };

  const step = (dt: number) => {
    const spread = anchorAt(shown, anchor);
    // On narrow screens the pile sits above the copy rather than beside it.
    if (camera.aspect < 0.8) { anchor.x *= 0.3; anchor.y += 7; }
    const scrollKick = (shown - lastShown) * 60;
    lastShown = shown;
    plane.constant = -anchor.z;
    ray.setFromCamera(pointerNdc, camera);
    const hasPointer = presence > 0.01 && ray.ray.intersectPlane(plane, pointerWorld) !== null;
    for (const body of bodies) {
      const p = body.mesh.position;
      // Pull towards the body's own place in the cluster.
      toward.copy(body.home).multiplyScalar(spread).add(anchor).sub(p);
      body.v.addScaledVector(toward, dt * 3.6);
      // Scrolling stirs the pile.
      body.v.y += scrollKick * 0.6 * dt * (0.5 + ((body.home.x + 4) % 1));
      if (hasPointer) {
        delta.copy(p).sub(pointerWorld);
        const d = delta.length();
        if (d < 4.5 && d > 1e-3) {
          const push = (1 - d / 4.5) * 30 * presence;
          body.v.addScaledVector(delta.normalize(), push * dt);
          body.w.x += delta.y * push * dt * 0.08; body.w.y -= delta.x * push * dt * 0.08;
        }
      }
    }
    // Bodies shoulder each other apart, and a knock sets them turning.
    for (let i = 0; i < bodies.length; i++) for (let j = i + 1; j < bodies.length; j++) {
      const a = bodies[i], b = bodies[j];
      delta.copy(b.mesh.position).sub(a.mesh.position);
      const d = delta.length(), min = radius * 1.72;
      if (d < min && d > 1e-4) {
        const overlap = (min - d) / min;
        delta.multiplyScalar(1 / d);
        a.v.addScaledVector(delta, -overlap * 18 * dt); b.v.addScaledVector(delta, overlap * 18 * dt);
        a.w.z += overlap * dt * 2; b.w.z -= overlap * dt * 2;
      }
    }
    const drag = Math.exp(-dt * 3.2), spin = Math.exp(-dt * 0.9);
    for (const body of bodies) {
      body.v.multiplyScalar(drag);
      body.w.multiplyScalar(spin);
      body.mesh.position.addScaledVector(body.v, dt);
      body.mesh.rotation.x += (body.w.x + 0.04) * dt; body.mesh.rotation.y += (body.w.y + 0.03) * dt; body.mesh.rotation.z += body.w.z * dt;
    }
  };

  const tick = (now: number) => {
    frame = 0;
    const dt = Math.min(1 / 30, (now - last) / 1000);
    last = now;
    shown += (target - shown) * (1 - Math.exp(-dt * 5));
    step(dt);
    renderer.render(scene, camera);
    if (active && !options.still) frame = requestAnimationFrame(tick);
  };
  const wake = () => { if (!frame && active && !options.still) { last = performance.now(); frame = requestAnimationFrame(tick); } };
  const still = () => {
    // Reduced motion: let the pile settle once, then draw a single frame whenever the page moves.
    for (let i = 0; i < 240; i++) step(1 / 60);
    renderer.render(scene, camera);
  };

  const observer = new ResizeObserver(() => { resize(); if (options.still) renderer.render(scene, camera); });
  observer.observe(host);
  resize();
  if (options.still) still(); else wake();

  return {
    progress(value) {
      target = Math.min(1, Math.max(0, value));
      if (options.still) { shown = target; lastShown = shown; for (let i = 0; i < 30; i++) step(1 / 60); renderer.render(scene, camera); }
    },
    pointer(x, y, inside) { pointerNdc.set(x * 2 - 1, y * 2 - 1); presence = inside && !options.still ? 1 : 0; },
    running(value) { active = value; if (value) wake(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } },
    dispose() {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      geometry.dispose(); materials.forEach(material => material.dispose());
      room.dispose(); pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
