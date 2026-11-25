import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

/** The landing page's world: one WebGL space behind every section, black, crossed by ribbons and discs of
 *  hundreds of fine lines in the warm colour of culture medium. The camera travels through it as the page
 *  scrolls, a slow light runs along the lines, and light gathers under the pointer. Lines are drawn
 *  analytically in the fragment shader (one pixel wide at any distance, faded to their average where they
 *  grow denser than the pixels), so the fine moiré stays clean instead of aliasing. */
export type LineWorld = {
  /** Page progress, 0 at the top and 1 at the bottom. */
  progress(value: number): void;
  pointer(x: number, y: number, inside: boolean): void;
  running(value: boolean): void;
  dispose(): void;
};

type Options = { still: boolean; compact: boolean };

const VERTEX = /* glsl */`
attribute vec2 grid;
varying vec2 vGrid;varying float vDepth;varying vec3 vNormal;varying vec3 vView;
void main(){
  vGrid=grid;
  vec4 world=modelMatrix*vec4(position,1.);
  vec4 view=viewMatrix*world;
  vDepth=-view.z;vView=normalize(-view.xyz);
  vNormal=normalize(normalMatrix*normal);
  gl_Position=projectionMatrix*view;
}`;

const FRAGMENT = /* glsl */`
uniform float count;uniform float time;uniform float speed;uniform vec3 lit;uniform vec3 shade;
uniform vec2 pointer;uniform float presence;uniform vec2 resolution;uniform float near;uniform float far;uniform float gain;uniform float edge;uniform float ends;
varying vec2 vGrid;varying float vDepth;varying vec3 vNormal;varying vec3 vView;
void main(){
  // One line per unit of x across the ribbon: about a pixel wide wherever it is.
  float x=vGrid.y*count;float w=max(fwidth(x),1e-4);
  float gap=.5-abs(fract(x)-.5);
  float line=1.-clamp(gap/w,0.,1.);
  // Where lines crowd tighter than the pixels, show their average instead of shimmering.
  line=mix(line,min(w,1.)*.9,smoothstep(.3,.7,w));
  // Light that grazes the surface: lines turning away from the eye glow, as on brushed metal.
  float facing=abs(dot(normalize(vNormal),vView));
  float sheen=mix(.35,1.,pow(1.-facing,1.6));
  // A slow wave of light travelling along the lines.
  float run=fract(vGrid.x-time*speed);
  float wave=.55+.45*exp(-pow((run-.5)*6.,2.));
  // Soft edges across the ribbon, and depth.
  float across=smoothstep(0.,edge,vGrid.y)*smoothstep(1.,1.-edge,vGrid.y);
  // Bands thin out towards their ends; a disc closes on itself, so it has none.
  if(ends>0.) across*=smoothstep(0.,ends,vGrid.x)*smoothstep(1.,1.-ends,vGrid.x);
  float depth=smoothstep(far,far*.55,vDepth)*smoothstep(near,near*2.2,vDepth);
  // Light under the pointer.
  vec2 q=(gl_FragCoord.xy/resolution-pointer)*vec2(resolution.x/resolution.y,1.);
  float glow=exp(-dot(q,q)*14.)*presence;
  vec3 colour=mix(shade,lit,clamp(sheen*wave+glow*.8,0.,1.));
  float a=line*across*depth*(sheen*wave*.85+glow*1.4)*gain;
  gl_FragColor=vec4(colour*a,1.);
}`;

type Ribbon = { mesh: THREE.Mesh; material: THREE.ShaderMaterial; spin: THREE.Vector3 };

/** A flat ring seen in perspective: its lines are concentric circles. */
function disc(inner: number, outer: number, segments: number, rings: number) {
  const position: number[] = [], grid: number[] = [], index: number[] = [];
  for (let j = 0; j <= rings; j++) {
    const v = j / rings, r = inner + (outer - inner) * v;
    for (let i = 0; i <= segments; i++) {
      const u = i / segments, a = u * Math.PI * 2;
      position.push(Math.cos(a) * r, Math.sin(a) * r, 0);
      grid.push(u, v);
    }
  }
  for (let j = 0; j < rings; j++) for (let i = 0; i < segments; i++) {
    const a = j * (segments + 1) + i, b = a + segments + 1;
    index.push(a, b, a + 1, b, b + 1, a + 1);
  }
  return build(position, grid, index);
}

/** A band swept along a wide arc, turning about its own length: its lines run with it. */
function band(radius: number, width: number, sweep: number, twist: number, rise: number, segments: number, across: number) {
  const position: number[] = [], grid: number[] = [], index: number[] = [];
  for (let i = 0; i <= segments; i++) {
    const u = i / segments, a = (u - 0.5) * sweep;
    const centre = new THREE.Vector3(Math.cos(a) * radius, Math.sin(u * Math.PI) * rise, Math.sin(a) * radius);
    const tangent = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
    const outward = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
    const turn = (u - 0.5) * twist;
    const side = outward.clone().multiplyScalar(Math.cos(turn)).add(new THREE.Vector3(0, 1, 0).multiplyScalar(Math.sin(turn)));
    side.sub(tangent.clone().multiplyScalar(side.dot(tangent))).normalize();
    for (let j = 0; j <= across; j++) {
      const v = j / across, p = centre.clone().addScaledVector(side, (v - 0.5) * width);
      position.push(p.x, p.y, p.z);
      grid.push(u, v);
    }
  }
  for (let i = 0; i < segments; i++) for (let j = 0; j < across; j++) {
    const a = i * (across + 1) + j, b = a + across + 1;
    index.push(a, b, a + 1, b, b + 1, a + 1);
  }
  return build(position, grid, index);
}

function build(position: number[], grid: number[], index: number[]) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
  geometry.setAttribute("grid", new THREE.Float32BufferAttribute(grid, 2));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

/** Camera stops down the page, in page-progress order; positions and aims are joined by smooth curves. */
const STOPS: { at: number; cam: [number, number, number]; look: [number, number, number] }[] = [
  { at: 0.0, cam: [0, 0.4, 16], look: [2.2, 0, 0] },
  { at: 0.12, cam: [-1.2, 0.2, 12.5], look: [3.4, -0.4, -2] },
  { at: 0.3, cam: [-4.5, 1.6, 8.5], look: [1.5, -0.3, -3] },
  { at: 0.5, cam: [2.5, -1.2, 9.5], look: [-0.5, 0.4, -4] },
  { at: 0.68, cam: [6.5, 0.6, 5.5], look: [0, 0, -6] },
  { at: 0.84, cam: [1.0, 2.4, 11.5], look: [3, 0, -4] },
  { at: 1.0, cam: [-2.0, 0.8, 14], look: [3.5, 0.2, -2] },
];

export function mountLineWorld(host: HTMLElement, options: Options): LineWorld | null {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: options.compact ? "low-power" : "high-performance" });
  } catch {
    return null;
  }
  const ratio = Math.min(devicePixelRatio, options.compact ? 1.5 : 1.75);
  renderer.setPixelRatio(ratio);
  renderer.setClearColor(0x000000, 1);
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 80);
  const resolution = new THREE.Vector2(1, 1);
  const pointerAt = new THREE.Vector2(0.5, 0.5);
  const uniforms = { time: { value: 0 }, pointer: { value: pointerAt }, presence: { value: 0 }, resolution: { value: resolution } };
  const detail = options.compact ? 0.55 : 1;
  const ribbons: Ribbon[] = [];
  const add = (geometry: THREE.BufferGeometry, place: { p: [number, number, number]; r: [number, number, number] }, look: { count: number; speed: number; gain: number; edge: number; ends?: number }, spin: [number, number, number]) => {
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX, fragmentShader: FRAGMENT, transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
      uniforms: { ...uniforms, count: { value: look.count }, speed: { value: look.speed }, gain: { value: look.gain }, edge: { value: look.edge }, ends: { value: look.ends ?? 0 },
        lit: { value: new THREE.Color(0xf6d2c0) }, shade: { value: new THREE.Color(0x8a4a33) }, near: { value: 0.6 }, far: { value: 46 } },
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = 1;
    mesh.position.set(...place.p);
    mesh.rotation.set(...place.r);
    scene.add(mesh);
    ribbons.push({ mesh, material, spin: new THREE.Vector3(...spin) });
  };

  // One thick glossy line (after Lusion) runs through the whole space, past every stop of the camera; it
  // reflects a soft studio room, so it reads as a solid object among the fine lines.
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const route = new THREE.CatmullRomCurve3([
    [-14, 10, -28], [-2, 7, -20], [9, 4.5, -15], [14, 0, -17], [9, -4.5, -21], [3, -2.5, -18], [8, 3, -14], [15, 4.5, -18], [22, 0, -26],
  ].map(p => new THREE.Vector3(...(p as [number, number, number]))), false, "centripetal", 0.5);
  const tubeMaterial = new THREE.MeshPhysicalMaterial({ color: 0xd8705e, roughness: 0.16, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.08, envMap: room, envMapIntensity: 1.25 });
  const tube = new THREE.Mesh(new THREE.TubeGeometry(route, Math.round(900 * detail), options.compact ? 0.18 : 0.21, 28, false), tubeMaterial);
  tube.renderOrder = 0;
  scene.add(tube);

  // The great disc: a ring of concentric lines with a dark heart, tilted away to the right.
  add(disc(2.6, 9.5, Math.round(360 * detail), 24), { p: [7.5, -0.6, -9], r: [-1.05, 0.55, 0.2] }, { count: 64, speed: 0.012, gain: 0.95, edge: 0.06 }, [0, 0, 0.004]);
  // Long bands sweeping past the reading column, each turning once along its length.
  add(band(11, 3.4, 2.1, 2.6, 1.6, Math.round(420 * detail), 18), { p: [-2, -1.5, -8], r: [0.25, 0.4, -0.18] }, { count: 46, speed: 0.02, gain: 0.8, edge: 0.12, ends: 0.16 }, [0, 0.0025, 0]);
  add(band(8.5, 2.2, 2.6, -3.4, -1.2, Math.round(380 * detail), 14), { p: [4, 2.5, -14], r: [-0.4, -0.9, 0.35] }, { count: 34, speed: 0.016, gain: 0.7, edge: 0.14, ends: 0.16 }, [0, -0.002, 0]);
  add(band(15, 5.5, 1.6, 1.8, 2.4, Math.round(420 * detail), 22), { p: [-6, 3, -20], r: [0.9, 0.2, 0.6] }, { count: 60, speed: 0.01, gain: 0.6, edge: 0.1, ends: 0.16 }, [0.0015, 0, 0]);
  // A small, close disc that drifts across the middle of the page.
  add(disc(0.9, 3.2, Math.round(220 * detail), 12), { p: [-5.5, -3.2, -3], r: [-0.4, -0.8, 0.1] }, { count: 28, speed: 0.025, gain: 0.8, edge: 0.08 }, [0, 0, -0.006]);

  const camCurve = new THREE.CatmullRomCurve3(STOPS.map(stop => new THREE.Vector3(...stop.cam)), false, "centripetal");
  const lookCurve = new THREE.CatmullRomCurve3(STOPS.map(stop => new THREE.Vector3(...stop.look)), false, "centripetal");
  // Map page progress onto the curves through the stops' own positions on the page.
  const along = (p: number) => {
    const k = STOPS.findIndex((stop, i) => i < STOPS.length - 1 && p <= STOPS[i + 1].at);
    const i = k < 0 ? STOPS.length - 2 : k;
    const a = STOPS[i], b = STOPS[i + 1];
    return (i + Math.min(1, Math.max(0, (p - a.at) / (b.at - a.at)))) / (STOPS.length - 1);
  };

  let target = 0, shown = 0, presence = 0, presenceTarget = 0;
  const pointerTarget = new THREE.Vector2(0.5, 0.5);
  let active = true, frame = 0, last = performance.now(), clock = 18;
  const cam = new THREE.Vector3(), look = new THREE.Vector3();

  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight;
    renderer.setSize(width, height, false);
    renderer.getDrawingBufferSize(resolution);
    camera.aspect = width / Math.max(1, height);
    // Narrow screens see the world from further back, so the discs still frame the copy.
    camera.fov = camera.aspect < 0.8 ? 52 : 34;
    camera.updateProjectionMatrix();
  };
  const draw = () => {
    const t = along(shown);
    camCurve.getPoint(t, cam);
    lookCurve.getPoint(t, look);
    camera.position.copy(cam);
    camera.lookAt(look);
    uniforms.time.value = clock;
    uniforms.presence.value = presence;
    renderer.render(scene, camera);
  };
  const tick = (now: number) => {
    frame = 0;
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!options.still) {
      clock += dt;
      for (const ribbon of ribbons) { ribbon.mesh.rotation.x += ribbon.spin.x * dt * 6; ribbon.mesh.rotation.y += ribbon.spin.y * dt * 6; ribbon.mesh.rotation.z += ribbon.spin.z * dt * 6; }
    }
    const ease = options.still ? 1 : 1 - Math.exp(-dt * 4.5);
    shown += (target - shown) * ease;
    presence += (presenceTarget - presence) * (1 - Math.exp(-dt * 3));
    pointerAt.lerp(pointerTarget, 1 - Math.exp(-dt * 6));
    draw();
    const settling = Math.abs(target - shown) > 1e-4 || Math.abs(presenceTarget - presence) > 1e-3;
    if (active && (!options.still || settling)) frame = requestAnimationFrame(tick);
  };
  const wake = () => { if (!frame && active) { last = performance.now(); frame = requestAnimationFrame(tick); } };

  const observer = new ResizeObserver(() => { resize(); if (options.still) draw(); wake(); });
  observer.observe(host);
  resize();
  draw();
  wake();

  return {
    progress(value) { target = Math.min(1, Math.max(0, value)); if (options.still) shown = target; wake(); },
    pointer(x, y, inside) { pointerTarget.set(x, y); presenceTarget = inside && !options.still ? 1 : 0; wake(); },
    running(value) { active = value; if (value) wake(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } },
    dispose() {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      for (const ribbon of ribbons) { ribbon.mesh.geometry.dispose(); ribbon.material.dispose(); }
      tube.geometry.dispose(); tubeMaterial.dispose(); room.dispose(); pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
