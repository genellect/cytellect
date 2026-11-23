import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

/** A trophy blown from laboratory glass, holding culture medium, turning slowly under studio light. */
export function mountAwardTrophy(canvas: HTMLCanvasElement, still: boolean): () => void {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0e1613);
  scene.backgroundIntensity = 1;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = environment;

  const camera = new THREE.PerspectiveCamera(26, 1, 0.1, 50);
  camera.position.set(0, 1.55, 8.6);
  camera.lookAt(0, 1.3, 0);

  const trophy = new THREE.Group();
  scene.add(trophy);

  const glass = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, metalness: 0, roughness: 0.02, transmission: 1, thickness: 0.08, ior: 1.48,
    envMapIntensity: 0.8, clearcoat: 1, clearcoatRoughness: 0.02, specularIntensity: 1, side: THREE.DoubleSide,
  });
  const medium = new THREE.MeshPhysicalMaterial({
    color: 0xe58a7b, roughness: 0.18, transmission: 0, thickness: 1.2, ior: 1.33, sheen: 0.4, sheenColor: new THREE.Color(0xffd2c4),
    attenuationColor: new THREE.Color(0xd9655a), attenuationDistance: 0.9, envMapIntensity: 0.9,
  });

  // The cup, stem and foot in one turned profile (radius, height).
  const profile = [
    [0.0, 0.0], [1.05, 0.0], [1.08, 0.06], [1.0, 0.12], [0.62, 0.2], [0.2, 0.32], [0.13, 0.5], [0.12, 0.95],
    [0.16, 1.05], [0.3, 1.16], [0.62, 1.34], [0.86, 1.62], [0.98, 2.0], [1.02, 2.45], [1.04, 2.62],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const body = new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(profile).getPoints(240), 200), glass);
  trophy.add(body);

  // Culture medium filling the lower half of the cup.
  const fill = [[0.0, 1.2], [0.28, 1.2], [0.58, 1.38], [0.8, 1.64], [0.9, 1.92], [0.0, 1.92]].map(([x, y]) => new THREE.Vector2(x, y));
  trophy.add(new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(fill).getPoints(120), 160), medium));

  // A backdrop the glass bends: dark stage with a warm pool of light behind the cup.
  const backdrop = document.createElement("canvas");
  backdrop.width = backdrop.height = 512;
  const paint = backdrop.getContext("2d")!;
  const pool = paint.createRadialGradient(256, 220, 10, 256, 256, 300);
  pool.addColorStop(0, "#d99a88"); pool.addColorStop(0.14, "#6d4840"); pool.addColorStop(0.32, "#1f201c"); pool.addColorStop(0.46, "#0e1613");
  paint.fillStyle = pool; paint.fillRect(0, 0, 512, 512);
  const backdropTexture = new THREE.CanvasTexture(backdrop);
  backdropTexture.colorSpace = THREE.SRGBColorSpace;
  const stage = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: backdropTexture, toneMapped: false }));
  stage.position.set(0, 1.4, -3.2);
  stage.scale.setScalar(1.6);
  scene.add(stage);

  // Two drawn-glass handles.
  for (const side of [-1, 1]) {
    const curve = new THREE.CubicBezierCurve3(
      new THREE.Vector3(side * 0.98, 2.3, 0), new THREE.Vector3(side * 1.75, 2.35, 0),
      new THREE.Vector3(side * 1.6, 1.55, 0), new THREE.Vector3(side * 0.82, 1.6, 0),
    );
    trophy.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.06, 20, false), glass));
  }

  // A soft key light from above and a warm rim from behind, read in the glass's highlights.
  const key = new THREE.SpotLight(0xffffff, 60, 20, Math.PI / 7, 0.6, 1.4);
  key.position.set(2.5, 7, 4);
  key.target.position.set(0, 1.2, 0);
  scene.add(key, key.target);
  const rim = new THREE.PointLight(0xf3b7a3, 18, 12);
  rim.position.set(-2.4, 2.6, -2.5);
  scene.add(rim);

  let frame = 0, visible = true, last = performance.now(), angle = 0.35;
  const resize = () => {
    const { clientWidth: w, clientHeight: h } = canvas;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const draw = () => { trophy.rotation.y = angle; renderer.render(scene, camera); };
  const tick = (now: number) => {
    frame = 0;
    angle += Math.min(now - last, 50) * 0.00018;
    last = now;
    draw();
    if (visible) frame = requestAnimationFrame(tick);
  };
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible && !still && !frame) { last = performance.now(); frame = requestAnimationFrame(tick); }
  });
  const sizes = new ResizeObserver(() => { resize(); draw(); });
  resize();
  draw();
  sizes.observe(canvas);
  if (!still) observer.observe(canvas);

  return () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
    sizes.disconnect();
    scene.traverse(object => { if (object instanceof THREE.Mesh) object.geometry.dispose(); });
    glass.dispose(); medium.dispose(); backdropTexture.dispose(); environment.dispose(); pmrem.dispose(); renderer.dispose();
  };
}
