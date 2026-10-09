import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export type CellSceneController = { dispose(): void; syncMotion(): void };

/* Renderer initialization and ownership/disposal pattern adapted from COMPASS
 * product-sculpture-engine.ts, 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
 * Copyright (c) 2026 Yuto Matsui. Owner-authorized Cytellect adaptation.
 * Geometry/materials are the Cytellect Blender asset; no measurements are performed.
 */
export async function mountCellScene(host: HTMLDivElement, isPaused: () => boolean, signal: AbortSignal, onContextLost: () => void): Promise<CellSceneController> {
  const response = await fetch("/marketing/cell-sculpture.glb", { signal });
  if (!response.ok) throw new Error("Cell scene unavailable");
  const loader = new GLTFLoader();
  // Decode embedded image buffers through img-src, without allowing blob fetches
  // in connect-src. GLTFLoader still owns object-URL creation and revocation.
  loader.register(parser => {
    parser.textureLoader = new THREE.TextureLoader(parser.options.manager);
    return { name: "CYTELLECT_embedded_images" };
  });
  const asset = await loader.parseAsync(await response.arrayBuffer(), "/marketing/");
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  let decodedNormalMaps = 0;
  asset.scene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
      if (material instanceof THREE.MeshStandardMaterial && material.normalMap?.image instanceof HTMLImageElement && material.normalMap.image.naturalWidth > 0) decodedNormalMaps++;
    }
  });
  const releaseAsset = () => { geometries.forEach(value => value.dispose()); materials.forEach(value => value.dispose()); textures.forEach(value => value.dispose()); };
  // The pinned Blender model requires its embedded surface texture.
  if (!decodedNormalMaps) { releaseAsset(); throw new Error("Cell surface unavailable"); }
  if (signal.aborted) { releaseAsset(); throw new DOMException("Aborted", "AbortError"); }
  let renderer: THREE.WebGLRenderer;
  try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); }
  catch (error) { releaseAsset(); throw error; }
  let cleanupMount = () => { releaseAsset(); renderer.dispose(); renderer.domElement.remove(); };
  try {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setClearColor(0x020817, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 60);
  camera.position.set(0, 0, 9);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  let environment: THREE.WebGLRenderTarget;
  try { environment = pmrem.fromScene(room, 0.04); } finally { room.dispose(); pmrem.dispose(); }
  cleanupMount = () => { releaseAsset(); environment.dispose(); renderer.dispose(); renderer.domElement.remove(); };
  scene.environment = environment.texture;
  scene.environmentIntensity = 0.045;

  const key = new THREE.DirectionalLight(new THREE.Color().setRGB(0.34, 0.62, 1, THREE.LinearSRGBColorSpace), 2.3); key.position.set(-3, 5, 6);
  const rim = new THREE.DirectionalLight(new THREE.Color().setRGB(0.11, 0.57, 1, THREE.LinearSRGBColorSpace), 4.8); rim.position.set(5, 2, -3);
  const fill = new THREE.DirectionalLight(0x17346c, 0.15); fill.position.set(-4, -3, 2);
  scene.add(key, rim, fill, new THREE.AmbientLight(0x152e61, 0.18));
  const bounds = new THREE.Box3().setFromObject(asset.scene);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const normalization = 4.8 / Math.max(size.x, size.y, size.z);
  const halfSize = size.clone().multiplyScalar(normalization / 2);
  // Include the complete animation envelope in the camera fit.
  const framedX = halfSize.x + halfSize.z * 0.16;
  const framedY = halfSize.y + halfSize.z * 0.025;
  const framedZ = halfSize.z + halfSize.x * 0.16 + halfSize.y * 0.025;
  const sculpture = new THREE.Group();
  asset.scene.position.sub(center);
  sculpture.add(asset.scene);
  sculpture.scale.setScalar(normalization);
  scene.add(sculpture);
  let visible = false;
  let frame = 0;
  let lastTime = 0;
  let lastRender = 0;
  let elapsed = 0;
  let disposed = false;
  let contextUnavailable = false;
  let renders = 0;
  const render = () => {
    if (disposed || contextUnavailable) return;
    sculpture.rotation.y = Math.sin(elapsed * 0.095) * 0.16;
    sculpture.rotation.x = Math.sin(elapsed * 0.07) * 0.025;
    renderer.render(scene, camera);
    host.dataset.renderCount = String(++renders);
  };
  // IntersectionObserver reports a frame or more late under load; never draw once the hero has left the viewport.
  const onScreen = () => { const { top, bottom } = host.getBoundingClientRect(); return bottom > 0 && top < innerHeight; };
  const animate = (time: number) => {
    frame = 0;
    if (disposed || contextUnavailable || !visible || document.hidden || isPaused()) { lastTime = 0; return; }
    if (!onScreen()) { visible = false; lastTime = 0; return; }
    if (lastTime) elapsed += Math.min((time - lastTime) / 1000, 0.1);
    lastTime = time;
    if (time - lastRender >= 32) { render(); lastRender = time; }
    frame = requestAnimationFrame(animate);
  };
  const syncMotion = () => {
    cancelAnimationFrame(frame); frame = 0; lastTime = 0;
    if (!disposed && !contextUnavailable && visible && !document.hidden && !isPaused()) frame = requestAnimationFrame(animate);
  };
  const resize = () => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    const verticalAngle = THREE.MathUtils.degToRad(camera.fov / 2);
    const horizontalAngle = Math.atan(Math.tan(verticalAngle) * camera.aspect);
    // Fit the complete rotating form below the navigation, including narrow windows.
    camera.position.z = Math.max(9, (Math.max(framedY / Math.tan(verticalAngle), framedX / Math.tan(horizontalAngle)) + framedZ) * 1.1);
    camera.updateProjectionMatrix();
    const halfWidth = Math.tan(horizontalAngle) * (camera.position.z - framedZ);
    sculpture.position.set(Math.min(2.4, Math.max(0, halfWidth - framedX * 1.1)), -0.08, 0);
    render();
  };
  const resizeObserver = new ResizeObserver(resize);
  const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; syncMotion(); });
  const contextLost = (event: Event) => { event.preventDefault(); contextUnavailable = true; visible = false; syncMotion(); onContextLost(); };
  const dispose = () => {
    disposed = true; cancelAnimationFrame(frame); resizeObserver.disconnect(); visibility.disconnect();
    document.removeEventListener("visibilitychange", syncMotion);
    renderer.domElement.removeEventListener("webglcontextlost", contextLost);
    releaseAsset(); environment.dispose(); renderer.dispose(); renderer.domElement.remove(); delete host.dataset.renderCount;
  };
  cleanupMount = dispose;
  resizeObserver.observe(host); visibility.observe(host);
  document.addEventListener("visibilitychange", syncMotion);
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  resize();
  return { syncMotion, dispose };
  } catch (error) { cleanupMount(); throw error; }
}
