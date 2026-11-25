import * as THREE from "three";

/** The landing page's 3D world: one dark hall with a polished floor, fixed behind every section. Nothing in it
 *  is modelled; everything in it is Cytellect's own material standing as a sheet of light: the hero film, the
 *  demo's screens, the bench photograph, and the film again at the far end. Each sheet lights the hall with the
 *  colour it is showing (the film's light changes with its cuts), lies mirrored in the floor, and the page's
 *  scroll walks the camera down the hall from one to the next. In the product tour the camera flies to the
 *  screen of the chosen tab. Captures and footage pass through unchanged: no colour management, no tone
 *  mapping, nothing drawn over the interface. */
export type PanelId = "stats" | "ai" | "figure" | "ask" | "table" | "conclusion" | "discussion" | "layout" | "size";
export type WorldPanel = { id: PanelId; src: string };
export type StationId = "hero" | "mission" | "product" | "tour" | "reasons" | "impact" | "invite";
/** A station holds between `from` and `to` (scroll offsets in px); the camera travels between stations. */
export type Station = { id: StationId; from: number; to: number };
export type SceneWorld = {
  stations(list: Station[]): void;
  scroll(y: number): void;
  pointer(x: number, y: number, inside: boolean): void;
  /** The playing hero film, or null for its poster. */
  film(video: HTMLVideoElement | null): void;
  /** The tour's shot (see SHOTS); `then` continues to a slower second one. */
  shot(index: number, then?: number): void;
  running(value: boolean): void;
  dispose(): void;
};
type Options = { poster: string; bench: string; panels: WorldPanel[] };

type V3 = [number, number, number];
type Pose = { p: V3; ry: number; o: number };
type View = { cam: V3; look: V3; shift: number };

const VOID = [0.018, 0.02, 0.027] as const;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerp3 = (a: V3, b: V3, t: number): V3 => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const smooth = (t: number) => { const x = clamp01(t); return x * x * x * (x * (x * 6 - 15) + 10); };
const ease = (t: number) => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const along = (c: V3, ry: number, forward: number, right: number, up: number): V3 =>
  [c[0] + Math.sin(ry) * forward + Math.cos(ry) * right, c[1] + up, c[2] + Math.cos(ry) * forward - Math.sin(ry) * right];

/* The hall. The floor is y = 0 and the page walks towards -z. */
const FILM = { p: [7.4, 4.52, 0] as V3, ry: -0.6, w: 16, h: 9 };
const CLUSTER: V3 = [0, 4.25, -62];
const BENCH = { p: [-7.4, 4.52, -118] as V3, ry: 0.6, w: 13.5, h: 9 };
const END = { p: [0, 5.7, -236] as V3, ry: 0, w: 19.2, h: 10.8 };

/** World width of each plate of the tour; the height follows the capture. */
const WIDTH: Record<PanelId, number> = { stats: 4.2, ai: 4.2, figure: 4.2, ask: 1.55, table: 4.9, conclusion: 2.5, discussion: 2.5, layout: 1.2, size: 1.2 };
const SCREENS: PanelId[] = ["stats", "ai", "figure"];
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
type Shot = View & { show: PanelId[]; move?: Partial<Record<PanelId, Partial<Pose>>> };
const facing = (pose: Pose, distance: number, right = 0, up = 0): Pick<Shot, "cam" | "look"> => {
  const look = along(pose.p, pose.ry, 0, right, up);
  return { look, cam: along(look, pose.ry, distance, 0, 0.12) };
};
/** The overview, then one shot per tab (LandingExperience). Measurement has two shots, so the wide table
 *  glides across the frame after the camera arrives. Positions are relative to CLUSTER. */
const TABLE: Partial<Pose> = { p: [2.4, -0.9, 1.2], ry: -0.38 };
const SHOTS: Shot[] = [
  { cam: [-1.9, 1.35, 9.6], look: [1.3, 0.2, -1.5], shift: 0.33, show: [...SCREENS] },
  { ...facing(AI, 7.8, 0.45, 0.3), shift: 0.24, show: [...SCREENS, "ask"], move: { stats: { o: 0 }, figure: { o: 0 } } },
  { cam: [0.2, -0.8, 7], look: [2, -0.9, 1.2], shift: 0.38, show: [...SCREENS, "table"], move: { table: TABLE, stats: { o: 0 }, ai: { o: 0 }, figure: { o: 0 } } },
  { cam: [0.55, -0.8, 6.8], look: [2.25, -0.9, 1.2], shift: 0.38, show: [...SCREENS, "table"], move: { table: TABLE, stats: { o: 0 }, ai: { o: 0 }, figure: { o: 0 } } },
  { cam: [0.7, 0.1, 10.2], look: [0.95, 0.2, 1.6], shift: 0.24, show: [...SCREENS, "conclusion", "discussion"], move: { stats: { p: [0.2, 0.05, -1.3], o: 0.42 }, ai: { o: 0 } } },
  { ...facing(FIGURE, 7.6, 0.35, 0.3), shift: 0.24, show: [...SCREENS, "layout", "size"], move: { stats: { o: 0 }, ai: { o: 0 } } },
];
const hidden = (id: PanelId): Pose => {
  const home = HOME[id];
  return SCREENS.includes(id) ? { ...home, o: 0.25 } : { p: along(home.p, home.ry, -1.2, 0, -0.5), ry: home.ry, o: 0 };
};
const poseIn = (shot: Shot, id: PanelId): Pose => shot.show.includes(id) ? { ...HOME[id], ...shot.move?.[id] } : hidden(id);
type Tour = View & { poses: Record<PanelId, Pose> };
const IDS = Object.keys(HOME) as PanelId[];
const tourOf = (shot: Shot): Tour => ({ cam: add(CLUSTER, shot.cam), look: add(CLUSTER, shot.look), shift: shot.shift,
  poses: Object.fromEntries(IDS.map(id => [id, poseIn(shot, id)])) as Record<PanelId, Pose> });
const mixTour = (a: Tour, b: Tour, t: number): Tour => ({ cam: lerp3(a.cam, b.cam, t), look: lerp3(a.look, b.look, t), shift: lerp(a.shift, b.shift, t),
  poses: Object.fromEntries(IDS.map(id => { const x = a.poses[id], y = b.poses[id]; return [id, { p: lerp3(x.p, y.p, t), ry: lerp(x.ry, y.ry, t), o: lerp(x.o, y.o, t) }]; })) as Record<PanelId, Pose> });

/** Where the camera stands at each station. */
function stationView(id: StationId, aspect: number, tour: View): View {
  // The distance from which a sheet fills the whole view.
  const cover = (sheet: { w: number; h: number }) => Math.min(sheet.h / 2 / Math.tan(THREE.MathUtils.degToRad(16)), sheet.w / 2 / Math.tan(THREE.MathUtils.degToRad(16)) / aspect) * 0.96;
  switch (id) {
    case "hero": return { cam: [-5.2, 3.4, 18.5], look: [0.6, 4.3, 0], shift: 0 };
    case "mission": return { cam: [-1.2, 3.5, -16], look: [-11, 9.2, -62], shift: 0 };
    case "product": return { cam: add(CLUSTER, [-1.5, 1.0, 27]), look: add(CLUSTER, [0.6, 2.6, -1.5]), shift: 0.33 };
    case "tour": return tour;
    case "reasons": return { cam: [5.2, 3.4, -99.5], look: [-0.6, 4.3, -118], shift: 0 };
    case "impact": return { cam: [0, 3.1, -150], look: [-22, -3.6, -236], shift: 0 };
    case "invite": return { cam: [0, END.p[1], END.p[2] + cover(END)], look: [0, END.p[1], END.p[2]], shift: 0 };
  }
}

const VERTEX = /* glsl */`
varying vec2 vUv;varying vec3 vWorld;
void main(){vUv=uv;vec4 w=modelMatrix*vec4(position,1.);vWorld=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`;
const COMMON = /* glsl */`
uniform vec3 eye;uniform vec2 fog;varying vec2 vUv;varying vec3 vWorld;
float box(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
float haze(){return smoothstep(fog.x,fog.y,distance(eye,vWorld));}`;
/** A sheet of light: the capture or footage inside a thin glass edge that catches a rim of light. */
const FACE = /* glsl */`
uniform sampler2D map;uniform vec2 size;uniform float radius;uniform float bezel;uniform float opacity;uniform float dim;uniform vec3 rim;
${COMMON}
void main(){
  vec2 p=(vUv-.5)*size;float outer=box(p,size*.5,radius);float aa=fwidth(outer)*1.2;
  float shape=1.-smoothstep(-aa,aa,outer);
  vec2 inner=size*.5-bezel;float inside=1.-smoothstep(-aa,aa,box(p,inner,max(radius-bezel,.004)));
  vec3 tex=texture2D(map,(p+inner)/(2.*inner)).rgb;
  vec3 glass=vec3(.06,.062,.068)+.04*vUv.y;
  float edge=1.-smoothstep(0.,aa*3.,abs(outer+aa*1.6));
  vec3 color=mix(glass,tex,inside)+rim*edge*.14;
  color=mix(color,vec3(${VOID.join(",")}),dim);
  gl_FragColor=vec4(color,shape*opacity*(1.-haze()));
}`;
/** The same sheet lying in the polished floor: sharp where it meets the floor, softer and fainter with height. */
const MIRROR = /* glsl */`
uniform sampler2D map;uniform vec2 size;uniform float radius;uniform float opacity;uniform float dim;uniform float lift;
${COMMON}
void main(){
  float h=vUv.y*size.y+lift;
  // The mirrored edges soften with height, as they do in a floor that is polished but not a mirror.
  float feather=.03+h*.2;
  vec2 p=(vUv-.5)*size;float shape=1.-smoothstep(-feather,.02,box(p,size*.5,radius));
  vec2 r=vec2(.0025,.006)*(1.+h*2.2);
  vec3 c=vec3(0.);float n=0.;
  for(int i=-3;i<=3;i++)for(int j=-2;j<=2;j++){float w=exp(-float(i*i)*.22-float(j*j)*.35);c+=texture2D(map,clamp(vUv+vec2(float(j),float(i))*r,0.,1.)).rgb*w;n+=w;}
  c/=n;
  // A polished floor mirrors most at a grazing angle and least straight down.
  float graze=1.-abs(normalize(eye-vWorld).y);
  float fade=exp(-h*.7)*(.1+.9*pow(graze,2.4))*.5;
  float g=(hash(gl_FragCoord.xy)-.5)/255.;
  gl_FragColor=vec4(c*fade*shape*opacity*(1.-dim)*(1.-haze())+g,1.);
}`;
/** The light a sheet throws into the air around it. */
const HALO = /* glsl */`
uniform vec2 size;uniform float spread;uniform vec3 tint;uniform float opacity;
${COMMON}
void main(){vec2 p=(vUv-.5)*(size+spread*2.);float d=max(box(p,size*.5,.3),0.);float a=exp(-d*d/(spread*spread*.2))*.5+exp(-d/(spread*.16))*.5;
  float g=(hash(gl_FragCoord.xy)-.5)*1.5/255.;
  gl_FragColor=vec4(tint*a*a*.1*opacity*(1.-haze())+g,1.);}`;
/** The polished floor: each sheet's light pools in front of it and falls off with distance. */
const FLOOR = /* glsl */`
#define N 5
uniform vec3 lamp[N];uniform vec3 lampDir[N];uniform vec3 lampColor[N];
${COMMON}
void main(){
  vec3 c=vec3(0.);
  for(int i=0;i<N;i++){vec2 d=vWorld.xz-lamp[i].xz;float l=length(d);vec2 n=d/max(l,.001);
    float facing=pow(max(dot(n,lampDir[i].xz),0.),1.4)*.92+.08;
    float reach=lamp[i].y;
    c+=lampColor[i]*facing/(1.+l*l/(reach*reach))*exp(-l/(reach*5.));}
  float view=distance(eye,vWorld);
  // Grazing light: the floor shows more of it towards the horizon.
  float graze=1.-abs(normalize(eye-vWorld).y);
  c*=.2+.62*pow(graze,3.);
  c*=1.-smoothstep(fog.x,fog.y,view);
  float g=(hash(gl_FragCoord.xy)-.5)*1.5/255.;
  gl_FragColor=vec4(c+g,1.);
}`;

type Sheet = {
  group: THREE.Group; mirror: THREE.Mesh; face: THREE.ShaderMaterial; reflection: THREE.ShaderMaterial; halo: THREE.ShaderMaterial;
  size: THREE.Vector2; tint: THREE.Color; power: number; lit: number; seed: number;
};

export async function mountSceneWorld(host: HTMLElement, options: Options, signal: AbortSignal): Promise<SceneWorld | null> {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
  } catch {
    return null;
  }
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(new THREE.Color(...VOID), 1);
  renderer.domElement.setAttribute("aria-hidden", "true");

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 400);
  const eye = { value: new THREE.Vector3() }, fog = { value: new THREE.Vector2(34, 150) };
  const mirrors = new THREE.Group();
  mirrors.scale.y = -1;
  scene.add(mirrors);

  const loader = new THREE.TextureLoader();
  const anisotropy = renderer.capabilities.getMaxAnisotropy();
  const sources = [options.poster, options.bench, ...options.panels.map(panel => panel.src)];
  let textures: THREE.Texture[];
  try {
    textures = await Promise.all(sources.map(src => loader.loadAsync(src)));
  } catch {
    renderer.dispose();
    return null;
  }
  if (signal.aborted) { textures.forEach(texture => texture.dispose()); renderer.dispose(); return null; }
  for (const texture of textures) { texture.colorSpace = THREE.NoColorSpace; texture.anisotropy = anisotropy; }

  // The colour a sheet is showing, read from a thumbnail of it: this is the colour of its light.
  const probe = document.createElement("canvas");
  probe.width = 16; probe.height = 9;
  const pen = probe.getContext("2d", { willReadFrequently: true });
  const colourOf = (image: CanvasImageSource, out: THREE.Color) => {
    if (!pen) return out;
    try {
      pen.drawImage(image, 0, 0, 16, 9);
      const data = pen.getImageData(0, 0, 16, 9).data;
      let r = 0, g = 0, b = 0;
      for (let i = 0; i < data.length; i += 4) { r += data[i]; g += data[i + 1]; b += data[i + 2]; }
      const n = data.length / 4 * 255;
      out.setRGB(r / n, g / n, b / n);
    } catch { /* a frame that cannot be read keeps the last colour */ }
    return out;
  };

  const geometry = new THREE.PlaneGeometry(1, 1);
  const sheets: Sheet[] = [];
  const sheet = (texture: THREE.Texture, width: number, height: number, style: { radius: number; bezel: number; spread: number; power: number }): Sheet => {
    const size = new THREE.Vector2(width, height);
    const tint = colourOf(texture.image as CanvasImageSource, new THREE.Color(0.8, 0.8, 0.8));
    const shared = { eye, fog, map: { value: texture }, size: { value: size }, radius: { value: style.radius } };
    const face = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FACE, transparent: true, depthWrite: false,
      uniforms: { ...shared, bezel: { value: style.bezel }, opacity: { value: 0 }, dim: { value: 0 }, rim: { value: new THREE.Color(0.95, 0.9, 0.88) } } });
    const reflection = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: MIRROR, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      uniforms: { ...shared, opacity: { value: 0 }, dim: { value: 0 }, lift: { value: 0 } } });
    const halo = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: HALO, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
      uniforms: { eye, fog, size: { value: size }, spread: { value: style.spread }, tint: { value: tint }, opacity: { value: 0 } } });
    const group = new THREE.Group();
    const glow = new THREE.Mesh(geometry, halo);
    glow.scale.set(width + style.spread * 2, height + style.spread * 2, 1);
    glow.position.z = -0.05;
    glow.renderOrder = 2;
    const plane = new THREE.Mesh(geometry, face);
    plane.scale.set(width, height, 1);
    plane.renderOrder = 3;
    group.add(glow, plane);
    scene.add(group);
    const mirror = new THREE.Mesh(geometry, reflection);
    mirror.renderOrder = 1;
    mirrors.add(mirror);
    const item = { group, mirror, face, reflection, halo, size, tint, power: style.power, lit: 0, seed: sheets.length * 1.7 };
    sheets.push(item);
    return item;
  };
  const place = (item: Sheet, p: V3, ry: number) => {
    item.group.position.set(p[0], p[1], p[2]);
    item.group.rotation.y = ry;
    item.mirror.position.copy(item.group.position);
    item.mirror.rotation.y = ry;
    item.mirror.scale.set(item.size.x, item.size.y, 1);
    item.reflection.uniforms.lift.value = Math.max(0, p[1] - item.size.y / 2) * 2;
  };

  const film = sheet(textures[0], FILM.w, FILM.h, { radius: 0.14, bezel: 0, spread: 7, power: 1 });
  const bench = sheet(textures[1], BENCH.w, BENCH.h, { radius: 0.14, bezel: 0, spread: 6.5, power: 0.85 });
  const end = sheet(textures[0], END.w, END.h, { radius: 0.2, bezel: 0, spread: 16, power: 1.6 });
  end.tint = film.tint; end.halo.uniforms.tint.value = film.tint;
  place(film, FILM.p, FILM.ry); place(bench, BENCH.p, BENCH.ry); place(end, END.p, END.ry);
  const plates = options.panels.map((panel, index) => {
    const texture = textures[index + 2], image = texture.image as { width: number; height: number };
    const screen = SCREENS.includes(panel.id), width = WIDTH[panel.id], bezel = screen ? 0.03 : 0.02;
    const item = sheet(texture, width, (width - bezel * 2) * image.height / image.width + bezel * 2, { radius: screen ? 0.09 : 0.06, bezel, spread: screen ? 1.5 : 0.8, power: screen ? 0.5 : 0.22 });
    // Interface captures are white; their light is a cool lab white rather than their average grey.
    item.tint.setRGB(0.78, 0.84, 0.95);
    return { id: panel.id, item, screen };
  });

  const lamps = { lamp: { value: Array.from({ length: 5 }, () => new THREE.Vector3(0, 1, 9999)) }, lampDir: { value: Array.from({ length: 5 }, () => new THREE.Vector3(0, 0, 1)) }, lampColor: { value: Array.from({ length: 5 }, () => new THREE.Color(0, 0, 0)) } };
  const floorMaterial = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FLOOR, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, uniforms: { eye, fog, ...lamps } });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.scale.set(700, 700, 1);
  floor.renderOrder = 0;
  scene.add(floor);

  host.appendChild(renderer.domElement);

  let stations: Station[] = [{ id: "hero", from: 0, to: 0 }];
  const born = performance.now();
  let target = 0, shown = 0, active = true, frame = 0, last = born;
  let width = 0, height = 0;
  let tour = tourOf(SHOTS[0]);
  let flight: { from: Tour; to: Tour; start: number; duration: number; then?: number } | null = null;
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  let video: HTMLVideoElement | null = null, videoTexture: THREE.VideoTexture | null = null, sampled = 0;
  const filmTint = new THREE.Color().copy(film.tint), lookAt = new THREE.Vector3();
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  /** The camera at a scroll offset, and how far it has arrived at the tour (0 to 1). */
  const viewAt = (y: number, aspect: number): View & { arrive: number } => {
    const view = (station: Station) => stationView(station.id, aspect, tour);
    const at = (station: Station) => ({ ...view(station), arrive: station.id === "tour" ? 1 : 0 });
    let previous = stations[0];
    for (const station of stations) {
      if (y <= station.from) {
        if (station === previous) return at(station);
        const t = smooth((y - previous.to) / Math.max(1, station.from - previous.to));
        const a = at(previous), b = at(station);
        return { cam: lerp3(a.cam, b.cam, t), look: lerp3(a.look, b.look, t), shift: lerp(a.shift, b.shift, t), arrive: lerp(a.arrive, b.arrive, t) };
      }
      if (y <= station.to) return at(station);
      previous = station;
    }
    return at(previous);
  };
  const overview = tourOf(SHOTS[0]);

  const resize = () => {
    width = host.clientWidth; height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };

  const setLamp = (index: number, item: Sheet, reach: number) => {
    const p = item.group.position, ry = item.group.rotation.y;
    lamps.lamp.value[index].set(p.x, reach, p.z);
    lamps.lampDir.value[index].set(Math.sin(ry), 0, Math.cos(ry));
    lamps.lampColor.value[index].copy(item.tint).multiplyScalar(item.power * item.lit);
  };

  const draw = (now: number) => {
    frame = 0;
    const dt = Math.min(0.05, (now - last) / 1000), time = (now - born) / 1000;
    last = now;
    // The camera follows the page with a little weight.
    shown += (target - shown) * (1 - Math.exp(-dt * 7));
    if (Math.abs(target - shown) < 0.2) shown = target;

    if (flight) {
      const t = Math.min(1, (now - flight.start) / flight.duration);
      tour = mixTour(flight.from, flight.to, ease(t));
      if (t >= 1) { const next = flight.then; flight = null; if (next !== undefined) fly(next, 7000); }
    }
    const view = viewAt(shown, camera.aspect);
    pointer.x += (pointer.tx - pointer.x) * (1 - Math.exp(-dt * 3.2)); pointer.y += (pointer.ty - pointer.y) * (1 - Math.exp(-dt * 3.2));
    camera.position.set(view.cam[0] + pointer.x * 0.5, view.cam[1] + pointer.y * 0.22 + Math.sin(time * 0.3) * 0.03, view.cam[2]);
    camera.lookAt(lookAt.set(view.look[0] + pointer.x * 0.12, view.look[1], view.look[2]));
    if (view.shift) camera.setViewOffset(width, height, -width * view.shift, 0, width, height); else camera.clearViewOffset();
    eye.value.copy(camera.position);

    // The film's light follows its footage.
    if (videoTexture && video && now - sampled > 320) { sampled = now; colourOf(video, filmTint); }
    film.tint.lerp(filmTint, 1 - Math.exp(-dt * 2.5));

    // The hall lights up once, as the page opens.
    const power = still.matches ? 1 : smooth((time - 0.15) / 1.6);
    film.lit = power;
    // Away from the tour the screens stand as the overview; the chosen tab's close-ups come out on arrival.
    const poses = mixTour(overview, tour, view.arrive).poses;
    for (const { id, item, screen } of plates) {
      const pose = poses[id];
      const p = add(CLUSTER, pose.p);
      place(item, [p[0], p[1] + Math.sin(time * 0.45 + item.seed) * 0.025, p[2]], pose.ry);
      // The screens sleep in the distance and wake as the camera reaches them; one it passes through lets it by.
      const distance = camera.position.distanceTo(item.group.position);
      const awake = smooth((52 - distance) / 26), near = smooth((distance - 1.2) / 2.2) * smooth((74 - distance) / 14);
      const shownPlate = (screen ? Math.min(1, pose.o * 1.4) : THREE.MathUtils.smoothstep(pose.o, 0.6, 1)) * near;
      item.lit = power * shownPlate * (screen ? Math.min(1, pose.o) : 1) * (0.16 + 0.84 * awake);
      item.face.uniforms.opacity.value = shownPlate * power;
      item.face.uniforms.dim.value = Math.max(screen ? 1 - Math.min(1, pose.o) : 0, (1 - awake) * 0.72);
      item.group.visible = item.mirror.visible = shownPlate > 0.005;
    }
    for (const item of sheets) {
      if (item !== film && item !== bench && item !== end) { item.reflection.uniforms.opacity.value = item.face.uniforms.opacity.value; item.reflection.uniforms.dim.value = item.face.uniforms.dim.value; item.halo.uniforms.opacity.value = item.lit; continue; }
      const distance = camera.position.distanceTo(item.group.position), z = camera.position.z;
      // Each sheet comes into view once the camera has passed the one before it.
      const near = item === end ? smooth((-120 - z) / 12) : smooth((distance - 2) / 5) * (item === bench ? smooth((-74 - z) / 14) : 1);
      if (item !== film) item.lit = power * near;
      item.face.uniforms.opacity.value = power * near;
      item.reflection.uniforms.opacity.value = power * near;
      item.halo.uniforms.opacity.value = item.lit * item.power;
    }
    setLamp(0, film, 11); setLamp(1, bench, 10.5); setLamp(2, end, 15);
    if (plates.length) {
      const screen = plates.find(plate => plate.id === "stats")!.item;
      setLamp(3, screen, 6);
      lamps.lampColor.value[3].multiplyScalar(2.2);
    }
    floor.position.set(camera.position.x, 0, camera.position.z - 120);
    renderer.render(scene, camera);
    if (active && !still.matches) frame = requestAnimationFrame(draw);
  };
  const request = () => { if (!frame && active) { last = performance.now(); frame = requestAnimationFrame(draw); } };
  function fly(index: number, duration = 1600, then?: number) {
    const to = tourOf(SHOTS[Math.min(SHOTS.length - 1, Math.max(0, index))]);
    if (still.matches) { tour = to; flight = null; } else flight = { from: tour, to, start: performance.now(), duration, then };
    request();
  }

  const observer = new ResizeObserver(() => { resize(); request(); });
  observer.observe(host);
  resize();
  request();

  return {
    stations(list) { if (list.length) stations = list; request(); },
    scroll(y) { target = y; if (still.matches) shown = y; request(); },
    pointer(x, y, inside) { pointer.tx = inside ? x * 2 - 1 : 0; pointer.ty = inside ? y * 2 - 1 : 0; },
    film(element) {
      if (element === video) return;
      videoTexture?.dispose();
      video = element; videoTexture = null;
      if (element) { videoTexture = new THREE.VideoTexture(element); videoTexture.colorSpace = THREE.NoColorSpace; videoTexture.anisotropy = anisotropy; }
      const map = videoTexture ?? textures[0];
      for (const item of [film, end]) { item.face.uniforms.map.value = map; item.reflection.uniforms.map.value = map; }
      if (!element) colourOf(textures[0].image as CanvasImageSource, filmTint);
      request();
    },
    shot(index, then) { fly(index, 1600, then); },
    running(value) { active = value; if (value) request(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } },
    dispose() {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      for (const item of sheets) { item.face.dispose(); item.reflection.dispose(); item.halo.dispose(); }
      geometry.dispose(); floor.geometry.dispose(); floorMaterial.dispose();
      textures.forEach(texture => texture.dispose()); videoTexture?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
