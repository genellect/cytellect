import * as THREE from "three";

/** The product tour on the landing page: Cytellect's screens, captured from the public demo, stand as glass
 *  plates in one bright space, and the camera flies to the screen of the tab the visitor chooses (summary and
 *  discussion, detection and measurement, AI set-up, statistics and figures). Each plate shows a capture as it
 *  is; nothing is drawn over the interface. */
export type PanelId = "stats" | "ai" | "figure" | "ask" | "table" | "conclusion" | "discussion" | "layout" | "size";
export type ExperiencePanel = { id: PanelId; src: string };
/** `show` flies to one shot; `then` continues to a second, slower one (the table gliding past). */
export type ExperienceController = { show(shot: number, then?: number): void; dispose(): void };

type V3 = [number, number, number];
type Pose = { p: V3; ry: number; o: number };
type Shot = { cam: V3; look: V3; shift: number; warm: number; show: PanelId[]; move?: Partial<Record<PanelId, Partial<Pose>>> };

/** World width of each plate; the height follows the capture. */
const WIDTH: Record<PanelId, number> = { stats: 4.2, ai: 4.2, figure: 4.2, ask: 1.55, table: 4.9, conclusion: 2.5, discussion: 2.5, layout: 1.2, size: 1.2 };
const SCREENS: PanelId[] = ["stats", "ai", "figure"];

const along = (c: V3, ry: number, forward: number, right: number, up: number): V3 =>
  [c[0] + Math.sin(ry) * forward + Math.cos(ry) * right, c[1] + up, c[2] + Math.cos(ry) * forward - Math.sin(ry) * right];

const AI: Pose = { p: [-4.9, 0.35, -2.6], ry: 0.5, o: 1 };
const FIGURE: Pose = { p: [4.9, -0.15, -2.6], ry: -0.5, o: 1 };
const HOME: Record<PanelId, Pose> = {
  stats: { p: [0, 0, 0], ry: 0, o: 1 },
  ai: AI,
  figure: FIGURE,
  ask: { p: along(AI.p, AI.ry, 1.2, 0.95, -0.42), ry: AI.ry, o: 1 },
  table: { p: [0.3, -2.75, 1.1], ry: 0, o: 1 },
  conclusion: { p: [1.0, 0.92, 1.55], ry: -0.05, o: 1 },
  discussion: { p: [1.2, -0.86, 1.9], ry: -0.05, o: 1 },
  layout: { p: along(FIGURE.p, FIGURE.ry, 1.3, 1.0, 0.5), ry: FIGURE.ry, o: 1 },
  size: { p: along(FIGURE.p, FIGURE.ry, 1.45, 1.05, -0.62), ry: FIGURE.ry, o: 1 },
};

/** A shot facing a plate. `up` lowers the aim below the plate's centre, which lifts the plate in the frame,
 *  clear of the tab cards along the bottom. */
const facing = (pose: Pose, distance: number, right = 0, up = 0): Pick<Shot, "cam" | "look"> => {
  const look = along(pose.p, pose.ry, 0, right, up);
  return { look, cam: along(look, pose.ry, distance, 0, 0.12) };
};

/** The overview, then one shot per tab (EXPERIENCE_SHOT in LandingExperience). Measurement has two shots, so
 *  the wide table glides across the frame after the camera arrives. */
const SHOTS: Shot[] = [
  { cam: [-1.9, 1.35, 9.6], look: [1.3, 0.2, -1.5], shift: 0.31, warm: 0.15, show: [...SCREENS] },
  { ...facing(AI, 7.4, 0.45, -0.3), shift: 0.17, warm: 0.2, show: [...SCREENS, "ask"], move: { stats: { o: 0 }, figure: { o: 0 } } },
  { cam: [-0.75, -2.45, 5.3], look: [-0.75, -2.75, 1.1], shift: 0.25, warm: 0.25, show: [...SCREENS, "table"] },
  { cam: [1.55, -2.45, 5.3], look: [1.55, -2.75, 1.1], shift: 0.25, warm: 0.35, show: [...SCREENS, "table"] },
  { cam: [0.7, -0.15, 10.2], look: [0.95, -0.35, 1.6], shift: 0.17, warm: 1, show: [...SCREENS, "conclusion", "discussion"], move: { stats: { p: [0.2, 0.05, -1.3], o: 0.42 } } },
  { ...facing(FIGURE, 7.2, 0.35, -0.45), shift: 0.17, warm: 0.3, show: [...SCREENS, "layout", "size"] },
];

const hidden = (id: PanelId): Pose => {
  const home = HOME[id];
  return SCREENS.includes(id) ? { ...home, o: 0.25 } : { p: along(home.p, home.ry, -1.2, 0, -0.5), ry: home.ry, o: 0 };
};
const poseIn = (shot: Shot, id: PanelId): Pose => shot.show.includes(id) ? { ...HOME[id], ...shot.move?.[id] } : hidden(id);

const PLATE_VERTEX = /* glsl */`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
/** A rounded glass plate: a frosted bezel with a bright rim, and the capture inside it. Colours pass through
 *  unchanged (no colour management or tone mapping), so the interface reads exactly as captured. */
const PLATE_FRAGMENT = /* glsl */`
uniform sampler2D map;uniform vec2 size;uniform float radius;uniform float bezel;uniform float opacity;uniform float dim;varying vec2 vUv;
float box(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
void main(){
  vec2 p=(vUv-.5)*size;float outer=box(p,size*.5,radius);float aa=fwidth(outer)*1.2;
  float shape=1.-smoothstep(-aa,aa,outer);
  vec2 inner=size*.5-bezel;float inside=1.-smoothstep(-aa,aa,box(p,inner,max(radius-bezel,.004)));
  vec3 tex=texture2D(map,(p+inner)/(2.*inner)).rgb;
  vec3 glass=vec3(.985,.99,.985)-.05*vUv.x+.035*vUv.y;
  float rim=1.-smoothstep(0.,aa*3.,abs(outer+aa*1.6));
  vec3 color=mix(glass,tex,inside)+rim*.35*(1.-inside);
  color=mix(color,vec3(.955,.962,.952),dim);
  gl_FragColor=vec4(color,shape*mix(.62,1.,inside)*opacity);
}`;
/** The plate's soft shadow on the light behind it. */
const SHADOW_FRAGMENT = /* glsl */`
uniform vec2 size;uniform float spread;uniform float opacity;varying vec2 vUv;
float box(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
void main(){vec2 p=(vUv-.5)*(size+spread*2.);float d=max(box(p,size*.5,.2),0.);float a=exp(-d*d/(spread*spread*.32));
  gl_FragColor=vec4(.09,.15,.13,a*.2*opacity);}`;
/** The space itself: lab-white light, falling a little toward the floor, with the warm colour of culture
 *  medium gathering behind the conclusion. */
const ROOM_FRAGMENT = /* glsl */`
uniform float warm;uniform float time;varying vec2 vUv;
float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
void main(){vec2 uv=vUv;
  vec3 color=mix(vec3(.918,.93,.92),vec3(.968,.972,.962),smoothstep(.15,.85,uv.y));
  vec2 g=uv-vec2(.66+.02*sin(time*.11),.42+.02*cos(time*.09));
  color=mix(color,vec3(.953,.82,.75),exp(-dot(g*vec2(1.3,1.9),g*vec2(1.3,1.9))*5.)*(.18+.6*warm));
  vec2 h=uv-vec2(.36,.86);color+=vec3(.035)*exp(-dot(h,h)*7.);
  color+=(hash(uv*vec2(1733.,977.)+time)-.5)*.012;
  gl_FragColor=vec4(color,1.);}`;

type Plate = { id: PanelId; group: THREE.Group; plate: THREE.ShaderMaterial; shadow: THREE.ShaderMaterial; seed: number };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerp3 = (a: V3, b: V3, t: number): V3 => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const ease = (t: number) => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;

/** Where everything stands: a shot, or a moment between two. */
type View = { cam: V3; look: V3; shift: number; warm: number; poses: Record<PanelId, Pose> };
const viewOf = (shot: Shot): View => ({ cam: shot.cam, look: shot.look, shift: shot.shift, warm: shot.warm,
  poses: Object.fromEntries((Object.keys(HOME) as PanelId[]).map(id => [id, poseIn(shot, id)])) as Record<PanelId, Pose> });
const mix = (a: View, b: View, t: number): View => ({ cam: lerp3(a.cam, b.cam, t), look: lerp3(a.look, b.look, t), shift: lerp(a.shift, b.shift, t), warm: lerp(a.warm, b.warm, t),
  poses: Object.fromEntries((Object.keys(HOME) as PanelId[]).map(id => { const x = a.poses[id], y = b.poses[id]; return [id, { p: lerp3(x.p, y.p, t), ry: lerp(x.ry, y.ry, t), o: lerp(x.o, y.o, t) }]; })) as Record<PanelId, Pose> });

export async function mountExperience(host: HTMLElement, panels: ExperiencePanel[], signal: AbortSignal): Promise<ExperienceController> {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0xf3f4f1, 1);
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);
  scene.add(camera);
  const room = new THREE.ShaderMaterial({ vertexShader: PLATE_VERTEX, fragmentShader: ROOM_FRAGMENT, uniforms: { warm: { value: 0 }, time: { value: 0 } }, depthWrite: false });
  const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), room);
  backdrop.position.z = -60;
  backdrop.renderOrder = -1;
  camera.add(backdrop);

  const loader = new THREE.TextureLoader();
  const anisotropy = renderer.capabilities.getMaxAnisotropy();
  const textures = await Promise.all(panels.map(panel => loader.loadAsync(panel.src)));
  if (signal.aborted) { textures.forEach(texture => texture.dispose()); renderer.dispose(); renderer.domElement.remove(); throw new DOMException("aborted", "AbortError"); }

  const plates: Plate[] = panels.map((panel, index) => {
    const texture = textures[index];
    texture.colorSpace = THREE.NoColorSpace;
    texture.anisotropy = anisotropy;
    const image = texture.image as { width: number; height: number };
    const width = WIDTH[panel.id], screen = SCREENS.includes(panel.id);
    const bezel = screen ? 0.075 : 0.05;
    const size = new THREE.Vector2(width, (width - bezel * 2) * image.height / image.width + bezel * 2);
    const plate = new THREE.ShaderMaterial({ vertexShader: PLATE_VERTEX, fragmentShader: PLATE_FRAGMENT, transparent: true, depthWrite: false,
      uniforms: { map: { value: texture }, size: { value: size }, radius: { value: screen ? 0.15 : 0.11 }, bezel: { value: bezel }, opacity: { value: 1 }, dim: { value: 0 } } });
    const spread = screen ? 0.55 : 0.4;
    const shadow = new THREE.ShaderMaterial({ vertexShader: PLATE_VERTEX, fragmentShader: SHADOW_FRAGMENT, transparent: true, depthWrite: false,
      uniforms: { size: { value: size }, spread: { value: spread }, opacity: { value: 1 } } });
    const group = new THREE.Group();
    const shade = new THREE.Mesh(new THREE.PlaneGeometry(size.x + spread * 2, size.y + spread * 2), shadow);
    shade.position.set(0.08, -0.28, -0.22);
    const face = new THREE.Mesh(new THREE.PlaneGeometry(size.x, size.y), plate);
    group.add(shade, face);
    scene.add(group);
    return { id: panel.id, group, plate, shadow, seed: index * 1.7 };
  });

  let width = 0, height = 0, frame = 0, visible = true;
  // The camera rests on a view, or flies from one view to a shot.
  let view = viewOf(SHOTS[0]);
  let flight: { from: View; to: View; start: number; duration: number; then?: number } | null = null;
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  const start = performance.now();
  const target = new THREE.Vector3();

  const resize = () => {
    width = host.clientWidth; height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    // The backdrop fills the view at its distance, with room for the view offset.
    const span = 2 * 60 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    backdrop.scale.set(span * camera.aspect * 1.6, span * 1.25, 1);
  };

  const draw = () => {
    frame = 0;
    if (!visible) return;
    const now = performance.now(), time = (now - start) / 1000;
    if (flight) {
      const t = Math.min(1, (now - flight.start) / flight.duration);
      view = mix(flight.from, flight.to, ease(t));
      if (t >= 1) { const next = flight.then; flight = null; if (next !== undefined) fly(next, 7000); }
    }
    pointer.x += (pointer.tx - pointer.x) * 0.05; pointer.y += (pointer.ty - pointer.y) * 0.05;
    camera.position.set(view.cam[0] + pointer.x * 0.18, view.cam[1] + pointer.y * 0.1 + Math.sin(time * 0.3) * 0.03, view.cam[2]);
    camera.lookAt(target.set(...view.look));
    // Shift the frame to the right of the text column.
    camera.setViewOffset(width, height, -width * view.shift, 0, width, height);
    room.uniforms.warm.value = view.warm;
    room.uniforms.time.value = time;
    for (const item of plates) {
      const { p, ry, o } = view.poses[item.id];
      item.group.position.set(p[0], p[1] + Math.sin(time * 0.45 + item.seed) * 0.025, p[2]);
      item.group.rotation.y = ry;
      item.group.visible = o > 0.005;
      // Close-ups appear only as the camera arrives and leave at once, so no plate lingers half-seen.
      const shown = SCREENS.includes(item.id) ? Math.min(1, o * 1.4) : THREE.MathUtils.smoothstep(o, 0.6, 1);
      item.plate.uniforms.opacity.value = shown;
      item.plate.uniforms.dim.value = SCREENS.includes(item.id) ? 1 - Math.min(1, o) : 0;
      item.shadow.uniforms.opacity.value = shown;
    }
    renderer.render(scene, camera);
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) frame = requestAnimationFrame(draw);
  };
  const request = () => { if (!frame) frame = requestAnimationFrame(draw); };
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  function fly(shot: number, duration = 1600, then?: number) {
    const to = viewOf(SHOTS[Math.min(SHOTS.length - 1, Math.max(0, shot))]);
    if (still()) { view = to; flight = null; } else flight = { from: view, to, start: performance.now(), duration, then };
    request();
  }

  const resizeObserver = new ResizeObserver(() => { resize(); request(); });
  resizeObserver.observe(host);
  const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) request(); });
  visibility.observe(host);
  const move = (event: PointerEvent) => { pointer.tx = event.clientX / innerWidth * 2 - 1; pointer.ty = -(event.clientY / innerHeight * 2 - 1); };
  addEventListener("pointermove", move, { passive: true });
  resize();
  request();

  return {
    show(shot, then) { fly(shot, 1600, then); },
    dispose() {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect(); visibility.disconnect();
      removeEventListener("pointermove", move);
      for (const item of plates) {
        item.group.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
        item.plate.dispose(); item.shadow.dispose();
      }
      textures.forEach(texture => texture.dispose());
      backdrop.geometry.dispose(); room.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
