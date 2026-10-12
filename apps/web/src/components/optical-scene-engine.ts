import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export type OpticalSceneController = { dispose(): void; syncMotion(): void };

/* Renderer initialization and ownership/disposal pattern adapted from COMPASS
 * product-sculpture-engine.ts, 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
 * Copyright (c) 2026 Yuto Matsui. Owner-authorized Cytellect adaptation.
 * Geometry/materials are the Cytellect Blender asset; no measurements are performed.
 */
export async function mountOpticalScene(host: HTMLDivElement, isPaused: () => boolean, signal: AbortSignal, onContextLost: () => void): Promise<OpticalSceneController> {
  const response = await fetch("/marketing/optical-assembly.glb", { signal });
  if (!response.ok) throw new Error("Optical scene unavailable");
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
  let meshCount = 0;
  asset.scene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    meshCount++;
    object.castShadow = !object.name.includes("floor");
    object.receiveShadow = true;
    geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      materials.add(material);
      if (material instanceof THREE.MeshPhysicalMaterial && material.transmission > 0) {
        material.thickness = material.name.includes("Smoked") ? 0.85 : 0.58;
        material.attenuationColor.set(0xd9f2ed);
        material.attenuationDistance = 5;
      }
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    }
  });
  const releaseAsset = () => { geometries.forEach(value => value.dispose()); materials.forEach(value => value.dispose()); textures.forEach(value => value.dispose()); };
  // Reject empty/corrupt models before replacing the rendered fallback.
  if (!meshCount) { releaseAsset(); throw new Error("Optical geometry unavailable"); }
  if (signal.aborted) { releaseAsset(); throw new DOMException("Aborted", "AbortError"); }
  let renderer: THREE.WebGLRenderer;
  try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); }
  catch (error) { releaseAsset(); throw error; }
  let cleanupMount = () => { releaseAsset(); renderer.dispose(); renderer.domElement.remove(); };
  try {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setClearColor(0xb7b5b0, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.96;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 180);
  camera.position.set(0, 0, 9);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  let environment: THREE.WebGLRenderTarget;
  try { environment = pmrem.fromScene(room, 0.04); } finally { room.dispose(); pmrem.dispose(); }
  cleanupMount = () => { releaseAsset(); environment.dispose(); renderer.dispose(); renderer.domElement.remove(); };
  scene.environment = environment.texture;
  scene.environmentIntensity = 1;

  scene.fog = new THREE.FogExp2(0xbcb9b2, 0.017);
  const key = new THREE.DirectionalLight(0xf4f6ff, 2.5); key.position.set(-3, 8, 7);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -15, right: 15, top: 15, bottom: -15, near: 0.1, far: 60 });
  key.shadow.bias = -0.0005;
  key.shadow.normalBias = 0.03;
  key.shadow.intensity = 0.22;
  const rim = new THREE.DirectionalLight(0xffc98e, 3); rim.position.set(7, 3, 1);
  const fill = new THREE.DirectionalLight(0x92bbff, 2); fill.position.set(-5, 4, -4);
  scene.add(key, rim, fill, new THREE.AmbientLight(0xdde6f0, 0.15), asset.scene);
  const planes: { object: THREE.Object3D; y: number; rotation: number }[] = [];
  asset.scene.traverse(object => {
    if (/Main_optical|Clear_refracting/.test(object.name)) {
      planes.push({ object, y: object.position.y, rotation: object.rotation.y });
    }
  });
  // One continuous authored world. Camera chapters follow page scroll, not
  // separate decorative canvases mounted by each content section.
  const positions = [
    new THREE.Vector3(2.2, 3.8, 12), new THREE.Vector3(-5, 3.3, 12),
    new THREE.Vector3(-8, 2.6, 11), new THREE.Vector3(-4, 4, 12),
    new THREE.Vector3(6, 3.5, 12), new THREE.Vector3(8, 2.8, 11),
  ];
  const targets = [
    new THREE.Vector3(-2.2, 0, 0), new THREE.Vector3(1.5, 0, -1),
    new THREE.Vector3(2, 0, -2), new THREE.Vector3(1, 0, -1),
    new THREE.Vector3(-1, 0, -1), new THREE.Vector3(-1.5, 0, 0),
  ];
  let progress = 0;
  let desiredProgress = 0;
  let portrait = false;
  let narrow = false;
  const look = new THREE.Vector3();
  const onScroll = () => {
    desiredProgress = Math.min(1, Math.max(0, window.scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight)));
  };
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
    progress += (desiredProgress - progress) * 0.08;
    const chapter = progress * (positions.length - 1);
    const index = Math.min(positions.length - 2, Math.floor(chapter));
    const mix = THREE.MathUtils.smoothstep(chapter - index, 0, 1);
    camera.position.lerpVectors(positions[index], positions[index + 1], mix);
    look.lerpVectors(targets[index], targets[index + 1], mix);
    if (portrait && progress < 0.16) {
      const weight = 1 - progress / 0.16;
      look.x += (narrow ? 0.9 : 2.3) * weight;
      look.y += 2.1 * weight;
      camera.position.z += 5 * weight;
    }
    camera.position.x += Math.sin(elapsed * 0.16) * 0.38;
    camera.position.y += Math.sin(elapsed * 0.12) * 0.16;
    planes.forEach(({object, y, rotation}, i) => {
      object.position.y = y + Math.sin(elapsed * 0.26 + i * 1.4) * 0.13;
      object.rotation.y = rotation + Math.sin(elapsed * 0.17 + i) * 0.055;
    });
    rim.position.x = 7 + Math.sin(elapsed * 0.23) * 3;
    fill.intensity = 1.8 + Math.sin(elapsed * 0.2) * 0.3;
    camera.lookAt(look);
    renderer.render(scene, camera);
    host.dataset.renderCount = String(++renders);
  };
  // Avoid drawing hidden hosts while IntersectionObserver catches up under load.
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
    portrait = width < 761 || height > width;
    narrow = width < 761;
    camera.updateProjectionMatrix();
    render();
  };
  const resizeObserver = new ResizeObserver(resize);
  const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; syncMotion(); });
  const contextLost = (event: Event) => { event.preventDefault(); contextUnavailable = true; visible = false; syncMotion(); onContextLost(); };
  const dispose = () => {
    disposed = true; cancelAnimationFrame(frame); resizeObserver.disconnect(); visibility.disconnect();
    document.removeEventListener("visibilitychange", syncMotion);
    window.removeEventListener("scroll", onScroll);
    renderer.domElement.removeEventListener("webglcontextlost", contextLost);
    releaseAsset(); key.shadow.map?.dispose(); environment.dispose(); renderer.dispose(); renderer.domElement.remove(); delete host.dataset.renderCount;
  };
  cleanupMount = dispose;
  resizeObserver.observe(host); visibility.observe(host);
  document.addEventListener("visibilitychange", syncMotion);
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  resize();
  return { syncMotion, dispose };
  } catch (error) { cleanupMount(); throw error; }
}
