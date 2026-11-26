import * as THREE from "three";

/** The hero's own 3D space: the visitor stands inside the film. Six screens close into a hexagonal room and all
 *  play the hero film; the one ahead fills most of the view, its neighbours stand at an angle on either side,
 *  and the polished floor and ceiling carry their reflections. Where two screens meet stands a column of light,
 *  blue rising to cyan, and the columns the pointer looks towards burn brighter. The pointer turns the view, a drag or a flick
 *  spins the room with inertia and it settles facing the nearest screen; touch does the same sideways and
 *  leaves vertical scrolling to the page. The footage passes through unchanged (no colour management, no tone
 *  mapping). */
export type HeroSpace = {
  /** The playing hero film, or null for its poster. */
  film(video: HTMLVideoElement | null): void;
  running(value: boolean): void;
  dispose(): void;
};

const SIDES = 6, WIDTH = 16, HEIGHT = 9, STEP = (Math.PI * 2) / SIDES;
const APOTHEM = WIDTH / (2 * Math.tan(Math.PI / SIDES));
/** How much of the view the screen ahead takes at rest; the rest shows the room around it. */
const FILL = 0.84;
/** Where the hero's copy leaves the film free: on a narrow screen the view rests a little right of centre. */
const FOCUS = 0.62;
const GROUND = 0x05070d;

const VERTEX = /* glsl */`varying vec2 vUv;varying vec3 vWorld;void main(){vUv=uv;vec4 w=modelMatrix*vec4(position,1.);vWorld=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}`;
/** A screen: the film, with a hairline of light along its edges. */
const SCREEN = /* glsl */`
uniform sampler2D map;uniform float lit;varying vec2 vUv;
void main(){
  vec3 c=texture2D(map,vUv).rgb;
  vec2 e=min(vUv,1.-vUv)*vec2(${WIDTH}.,${HEIGHT}.);
  float rim=exp(-min(e.x,e.y)*42.);
  gl_FragColor=vec4(c*lit+vec3(.72,.86,1.)*rim*.6*lit,1.);
}`;
/** The same screen in the polished floor or ceiling: sharp where they meet, softer and fainter further away. */
const MIRROR = /* glsl */`
uniform sampler2D map;uniform float lit;uniform float strength;uniform float above;uniform vec3 eye;varying vec2 vUv;varying vec3 vWorld;
float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
void main(){
  // Distance from the edge where the screen meets the floor (its foot) or the ceiling (its head).
  float h=mix(vUv.y,1.-vUv.y,above)*${HEIGHT}.;
  vec2 r=vec2(.003,.008)*(1.+h*1.8);
  vec3 c=vec3(0.);float n=0.;
  for(int i=-2;i<=2;i++)for(int j=-1;j<=1;j++){float w=exp(-float(i*i)*.3-float(j*j)*.5);c+=texture2D(map,clamp(vUv+vec2(float(j),float(i))*r,0.,1.)).rgb*w;n+=w;}
  float graze=1.-abs(normalize(eye-vWorld).y);
  float fade=exp(-h*.55)*(.25+.75*graze*graze)*strength;
  gl_FragColor=vec4(c/n*fade*lit+(hash(gl_FragCoord.xy)-.5)/255.,1.);
}`;

/** A column of light at a corner of the room: a bright core in a soft glow, blue at its foot and cyan at its head. */
const COLUMN = /* glsl */`
uniform float lit;uniform float power;varying vec2 vUv;
void main(){
  float x=abs(vUv.x-.5)*2.;
  float core=exp(-x*x*1400.)*.72,glow=exp(-x*x*22.)*.24+exp(-x*5.)*.07;
  float ends=smoothstep(0.,.22,vUv.y)*smoothstep(1.,.78,vUv.y);
  vec3 tint=mix(vec3(.3,.49,1.),vec3(.26,.85,1.),smoothstep(.2,.9,vUv.y));
  gl_FragColor=vec4((tint*glow+vec3(.6,.84,1.)*core)*ends*lit*power,1.);
}`;

/** `onLook` is told, every frame, where the view is turned by the pointer (−1 to 1 each way), so the hero's copy
 *  can stand a little in front of the room. */
export async function mountHeroSpace(host: HTMLElement, surface: HTMLElement, poster: string, signal: AbortSignal, onLook?: (x: number, y: number) => void): Promise<HeroSpace | null> {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
  } catch {
    return null;
  }
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(GROUND, 1);
  renderer.domElement.setAttribute("aria-hidden", "true");

  let still: THREE.Texture;
  try {
    still = await new THREE.TextureLoader().loadAsync(poster);
  } catch {
    renderer.dispose();
    return null;
  }
  if (signal.aborted) { still.dispose(); renderer.dispose(); return null; }
  const anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  still.colorSpace = THREE.NoColorSpace; still.anisotropy = anisotropy;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 200);
  camera.rotation.order = "YXZ";
  const map = { value: still as THREE.Texture }, lit = { value: 0 }, eye = { value: new THREE.Vector3() };
  const plane = new THREE.PlaneGeometry(WIDTH * 0.992, HEIGHT);
  const screen = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: SCREEN, uniforms: { map, lit } });
  const mirror = (strength: number, above: number) => new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: MIRROR, side: THREE.DoubleSide, uniforms: { map, lit, eye, strength: { value: strength }, above: { value: above } } });
  const floor = mirror(0.5, 0), ceiling = mirror(0.2, 1);
  // The room turns under the hand; the camera only looks around from where it stands.
  const room = new THREE.Group();
  scene.add(room);
  for (let k = 0; k < SIDES; k++) {
    const angle = k * STEP, x = Math.sin(angle) * APOTHEM, z = -Math.cos(angle) * APOTHEM;
    const face = new THREE.Mesh(plane, screen);
    face.position.set(x, 0, z); face.rotation.y = -angle;
    // The reflections are the screen folded down into the floor and up into the ceiling.
    const below = new THREE.Mesh(plane, floor), above = new THREE.Mesh(plane, ceiling);
    below.position.set(x, -HEIGHT - 0.1, z); below.rotation.y = -angle; below.scale.y = -1;
    above.position.set(x, HEIGHT + 0.1, z); above.rotation.y = -angle; above.scale.y = -1;
    room.add(face, below, above);
  }
  // The columns stand at the six corners, taller than the screens so the floor and ceiling carry them on.
  const RADIUS = APOTHEM / Math.cos(Math.PI / SIDES);
  const strip = new THREE.PlaneGeometry(5.2, HEIGHT * 2.6);
  const columns = Array.from({ length: SIDES }, (_, k) => {
    const angle = (k + 0.5) * STEP;
    const material = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: COLUMN, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { lit, power: { value: 0.6 } } });
    const mesh = new THREE.Mesh(strip, material);
    mesh.position.set(Math.sin(angle) * (RADIUS - 0.2), 0, -Math.cos(angle) * (RADIUS - 0.2));
    mesh.rotation.y = -angle;
    mesh.renderOrder = 2;
    room.add(mesh);
    return { angle, material };
  });

  let width = 1, height = 1, active = true, frame = 0, last = performance.now(), rest = 0, spanX = 1;
  const born = last;
  // The view: where the room has been spun to (yaw), and the look the pointer adds on top of it.
  let yaw = 0, speed = 0, held = false, lastX = 0, lastT = 0;
  const look = { x: 0, y: 0, tx: 0, ty: 0 };
  let video: HTMLVideoElement | null = null, videoTexture: THREE.VideoTexture | null = null;

  const resize = () => {
    width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false);
    const aspect = width / height;
    camera.aspect = aspect;
    // The screen ahead takes FILL of the view's height, or of its width on a very wide screen.
    const half = Math.min(HEIGHT / 2 / FILL, WIDTH / 2 / FILL / aspect);
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(half / APOTHEM));
    camera.updateProjectionMatrix();
    spanX = 2 * Math.atan(half * aspect / APOTHEM);
    // Where the screen is wider than the view, stand before the part of the film the copy leaves free.
    const crop = Math.max(0, 1 - (2 * half * aspect) / WIDTH);
    rest = (FOCUS - 0.5) * WIDTH * crop;
  };

  const draw = (now: number) => {
    frame = 0;
    const dt = Math.min(0.05, (now - last) / 1000), time = (now - born) / 1000;
    last = now;
    if (!held) {
      // A released room keeps turning, slows, and settles facing the nearest screen.
      yaw += speed * dt;
      speed *= Math.exp(-dt * 2.4);
      const nearest = Math.round(yaw / STEP) * STEP;
      if (Math.abs(speed) < 0.6) { yaw += (nearest - yaw) * (1 - Math.exp(-dt * 4.5)); speed *= Math.exp(-dt * 6); }
    }
    look.x += (look.tx - look.x) * (1 - Math.exp(-dt * 3.4)); look.y += (look.ty - look.y) * (1 - Math.exp(-dt * 3.4));
    // The room swings into place once, as the page opens.
    const arrive = 1 - Math.min(1, time / 2.2), opening = arrive * arrive * arrive;
    lit.value = Math.min(1, time / 1.1);
    room.rotation.y = yaw;
    camera.position.x = rest;
    camera.rotation.y = -look.x * 0.34 + opening * 0.95 + Math.sin(time * 0.31) * 0.012;
    camera.rotation.x = look.y * 0.14 + Math.sin(time * 0.23) * 0.006;
    eye.value.copy(camera.position);
    // The columns the view is turned towards burn brighter.
    const facing = camera.rotation.y - room.rotation.y;
    for (const column of columns) {
      const off = Math.atan2(Math.sin(-column.angle - facing), Math.cos(-column.angle - facing));
      const target = 0.42 + 0.5 * Math.exp(-off * off * 3.2);
      column.material.uniforms.power.value += (target - column.material.uniforms.power.value) * (1 - Math.exp(-dt * 4));
    }
    onLook?.(look.x, look.y);
    renderer.render(scene, camera);
    if (active) frame = requestAnimationFrame(draw);
  };
  const request = () => { if (!frame && active) { last = performance.now(); frame = requestAnimationFrame(draw); } };

  const interactive = (target: EventTarget | null) => target instanceof Element && target.closest("a,button,input,select,textarea") !== null;
  const down = (event: PointerEvent) => {
    if (event.button !== 0 || interactive(event.target)) return;
    held = true; speed = 0; lastX = event.clientX; lastT = event.timeStamp;
    surface.dataset.grabbing = "true";
  };
  const move = (event: PointerEvent) => {
    if (held) {
      // The room follows the hand: the film under the pointer stays under it.
      const turn = -(event.clientX - lastX) / width * spanX, elapsed = Math.max(1, event.timeStamp - lastT) / 1000;
      yaw += turn;
      speed = speed * 0.4 + (turn / elapsed) * 0.6;
      lastX = event.clientX; lastT = event.timeStamp;
    } else if (event.pointerType === "mouse") {
      const box = host.getBoundingClientRect();
      look.tx = THREE.MathUtils.clamp((event.clientX - box.left) / box.width - 0.5, -0.5, 0.5) * 2;
      look.ty = THREE.MathUtils.clamp(0.5 - (event.clientY - box.top) / box.height, -0.5, 0.5) * 2;
    }
  };
  const up = () => { if (held) { held = false; delete surface.dataset.grabbing; } };
  const leave = () => { look.tx = 0; look.ty = 0; };
  surface.addEventListener("pointerdown", down);
  addEventListener("pointermove", move, { passive: true });
  addEventListener("pointerup", up);
  addEventListener("pointercancel", up);
  surface.addEventListener("pointerleave", leave);

  const observer = new ResizeObserver(() => { resize(); request(); });
  observer.observe(host);
  resize();
  host.appendChild(renderer.domElement);
  request();

  return {
    film(element) {
      if (element === video) return;
      videoTexture?.dispose();
      video = element; videoTexture = null;
      if (element) { videoTexture = new THREE.VideoTexture(element); videoTexture.colorSpace = THREE.NoColorSpace; videoTexture.anisotropy = anisotropy; }
      map.value = videoTexture ?? still;
    },
    running(value) { active = value; if (value) request(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } },
    dispose() {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      surface.removeEventListener("pointerdown", down);
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      removeEventListener("pointercancel", up);
      surface.removeEventListener("pointerleave", leave);
      delete surface.dataset.grabbing;
      plane.dispose(); screen.dispose(); floor.dispose(); ceiling.dispose();
      strip.dispose(); for (const column of columns) column.material.dispose();
      still.dispose(); videoTexture?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
