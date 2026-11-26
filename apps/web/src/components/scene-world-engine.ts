import * as THREE from "three";

// The prism wall and the light field are adapted from the owner's portfolio (yuto-matsui-site,
// src/en/hero-prism-engine.ts, hero-light-engine.ts and page-light-engine.ts).
// Copyright (c) 2026 Yuto Matsui. All rights reserved.
// Reuse and adaptation expressly authorized by the owner for Cytellect.

/** The landing page's 3D stage: one canvas fixed behind every section.
 *
 *  Every picture on the page (the hero film, the demo's screens, the bench photograph) is carried by a wall of
 *  glass prisms that stands exactly where its frame sits in the page. At rest the front faces line up into the
 *  flat picture, drawn without shading, so footage and captures read exactly as delivered. A wall turns in a
 *  wave: into its picture as it scrolls into view, away from it as it leaves, and from one screen to the next
 *  when a tab is chosen; light from behind passes through the gaps that open while it turns. Behind the walls,
 *  ribbons of light drift through the dark, lean towards the pointer and move more slowly than the page. */
export type WallSpec = {
  id: string;
  /** The frame in the page this wall stands in (looked up again whenever the page changes). */
  element: () => HTMLElement | null;
  /** The pictures the wall can show. */
  sources: string[];
  /** Shows the page's film while one is playing; its first source is the poster. */
  film?: boolean;
  /** Indices of pictures wider than the frame, which glide sideways instead of being cropped. */
  glide?: number[];
  /** A wall at the top of the page opens by itself once, instead of with the scroll. */
  opens?: boolean;
};
export type SceneWorld = {
  /** Turn a wall to another of its pictures. */
  show(id: string, index: number): void;
  /** The playing film, or null for the poster. */
  film(video: HTMLVideoElement | null): void;
  pointer(x: number, y: number, inside: boolean): void;
  running(value: boolean): void;
  dispose(): void;
};
type Options = { walls: WallSpec[]; compact: boolean };

const TURN = (-2 * Math.PI) / 3;
const APOTHEM = 1 / (2 * Math.sqrt(3));
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
// Close to cubic-bezier(.2, .76, .2, 1): quick departure, long settle.
const easeTurn = (t: number) => { const inv = 1 - t; return 1 - inv * inv * inv * (1 - 0.35 * t); };
const smooth = (t: number) => { const x = clamp01(t); return x * x * (3 - 2 * x); };

function prismGeometry() {
  const corners: [number, number][] = [[-0.5, APOTHEM], [0.5, APOTHEM], [0, -2 * APOTHEM]];
  const position: number[] = [], normal: number[] = [], local: number[] = [], face: number[] = [];
  for (let k = 0; k < 3; k++) {
    const [px, pz] = corners[k], [qx, qz] = corners[(k + 1) % 3];
    const nx = qz - pz, nz = -(qx - px), length = Math.hypot(nx, nz);
    const quad: [number, number, number, number, number][] = [
      [px, -0.5, pz, 0, 0], [qx, -0.5, qz, 1, 0], [qx, 0.5, qz, 1, 1],
      [px, -0.5, pz, 0, 0], [qx, 0.5, qz, 1, 1], [px, 0.5, pz, 0, 1],
    ];
    for (const [x, y, z, u, v] of quad) { position.push(x, y, z); normal.push(nx / length, 0, nz / length); local.push(u, v); face.push(k); }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normal, 3));
  geometry.setAttribute("aLocal", new THREE.Float32BufferAttribute(local, 2));
  geometry.setAttribute("aFace", new THREE.Float32BufferAttribute(face, 1));
  return geometry;
}

const PRISM_VERTEX = /* glsl */`
attribute vec2 aLocal;attribute float aFace;
varying vec2 vLocal;varying float vFace;varying vec3 vNormal;varying vec3 vWorld;
void main(){vLocal=aLocal;vFace=aFace;vNormal=normalize(mat3(modelMatrix)*normal);vec4 world=modelMatrix*vec4(position,1.);vWorld=world.xyz;gl_Position=projectionMatrix*viewMatrix*world;}`;
/** One prism: two faces carry the current and the next picture, the third is dark glass. Shading and the
 *  hairline of light along the edges exist only while the prism is turned. */
const PRISM_FRAGMENT = /* glsl */`
uniform sampler2D uTexA;uniform sampler2D uTexB;uniform vec4 uCoverA;uniform vec4 uCoverB;
uniform float uIndex;uniform float uCount;uniform float uActivity;uniform float uFacePx;uniform vec2 uSize;uniform float uRadius;uniform vec3 uLight;
varying vec2 vLocal;varying float vFace;varying vec3 vNormal;varying vec3 vWorld;
float box(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
void main(){
  vec2 canvasUv=vec2((uIndex+vLocal.x)/uCount,vLocal.y);
  // The wall keeps the rounded corners of its frame.
  if(box((canvasUv-.5)*uSize,uSize*.5,uRadius)>0.)discard;
  float face=floor(vFace+.5);vec3 color;
  if(face<.5)color=texture2D(uTexA,canvasUv*uCoverA.xy+uCoverA.zw).rgb;
  else if(face<1.5)color=texture2D(uTexB,canvasUv*uCoverB.xy+uCoverB.zw).rgb;
  else color=mix(vec3(.008,.014,.013),vec3(.03,.06,.055),smoothstep(0.,1.,vLocal.y));
  vec3 n=normalize(vNormal);vec3 view=normalize(cameraPosition-vWorld);
  float lambert=.18+.82*max(dot(n,normalize(uLight)),0.);
  color*=mix(1.,lambert,uActivity);
  float spec=pow(max(dot(reflect(-normalize(uLight),n),view),0.),36.);
  color+=vec3(.9,1.,.97)*spec*.5*uActivity;
  float edge=exp(-min(vLocal.x,1.-vLocal.x)*uFacePx*1.15);
  color+=mix(vec3(.25,.85,.7),vec3(.95,.74,.66),vLocal.y)*edge*uActivity*1.2;
  gl_FragColor=vec4(color,1.);
}`;
/** The light behind a wall: a column of warm white falling off into the green and the pink of the page. */
const BACKLIGHT_FRAGMENT = /* glsl */`
uniform float uLight;uniform vec2 uSize;uniform float uRadius;varying vec2 vUv;
float box(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
void main(){
  // The light stays inside the frame of the wall: it is seen only through the gaps between turning prisms.
  if(box((vUv-.5)*uSize,uSize*.5,uRadius)>0.)discard;
  float column=exp(-pow((vUv.x-.5)*1.6,2.))*smoothstep(0.,.55,vUv.y)*smoothstep(1.05,.4,vUv.y);
  vec3 spectrum=mix(mix(vec3(.1,.62,.5),vec3(.2,.5,.95),smoothstep(.1,.55,vUv.y)),vec3(.95,.72,.64),smoothstep(.55,.98,vUv.y));
  gl_FragColor=vec4(mix(spectrum,vec3(1.,.98,.95),column*column*.8)*(.3+column)*uLight,1.);
}`;
const FLAT_VERTEX = /* glsl */`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
/** The light of the page: ribbons drifting through the dark, pulled towards the pointer, gathered into a source
 *  under it. Drawn small and stretched: the field is soft by nature. */
const FIELD_FRAGMENT = /* glsl */`
precision highp float;
uniform vec2 uRes;uniform float uTime;uniform vec2 uPointer;uniform float uPresence;uniform float uScroll;varying vec2 vUv;
float hash(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),u.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),u.x),u.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.02+vec2(3.1,7.7);a*=.5;}return v;}
vec3 spectrum(float t){
  vec3 c0=vec3(.012,.03,.027),c1=vec3(.03,.3,.26),c2=vec3(.09,.34,.66),c3=vec3(.62,.5,.6);
  t=clamp(t,0.,1.);
  if(t<.45)return mix(c0,c1,t/.45);
  if(t<.85)return mix(c1,c2,(t-.45)/.4);
  return mix(c2,c3,(t-.85)/.15);
}
void main(){
  float aspect=uRes.x/uRes.y;
  // The far layer moves more slowly than the page.
  vec2 p=vec2(vUv.x*aspect,vUv.y-uScroll*.22);
  vec2 m=vec2(uPointer.x*aspect,uPointer.y-uScroll*.22);
  float t=uTime*.03;
  vec2 toPointer=m-p;
  float pull=exp(-dot(toPointer,toPointer)*2.2)*uPresence;
  vec2 warped=p+toPointer*pull*.35;
  vec2 q=vec2(fbm(warped*1.2+vec2(0.,t)),fbm(warped*1.2+vec2(4.3,-t)));
  float f=fbm(warped*vec2(1.,2.4)+q*2.+vec2(t*.8,0.));
  float ribbon=pow(smoothstep(.36,.86,f),1.4);
  // Light keeps to the edges of the stage; the middle, where the copy sits, stays deeper.
  float edge=smoothstep(.1,.7,abs(vUv.x-.5)*2.);
  float field=ribbon*(.34+.66*edge);
  float d=length(toPointer);
  float spot=(exp(-d*d*9.)*.6+exp(-d*3.2)*.22)*uPresence;
  vec3 color=vec3(.018,.036,.032)+spectrum(field*.86+q.x*.1)*field*.55+spectrum(.5+q.y*.4)*spot*.5;
  color+=(hash(gl_FragCoord.xy+uTime)-.5)*.012;
  gl_FragColor=vec4(color,1.);
}`;

type Prism = { mesh: THREE.Mesh; material: THREE.ShaderMaterial };
type Wall = {
  spec: WallSpec; group: THREE.Group; prisms: Prism[]; backlight: THREE.Mesh; light: THREE.ShaderMaterial;
  element: HTMLElement | null; width: number; height: number; face: number;
  current: number; target: number | null; start: number; opened: number | null; tiltX: number; tiltY: number;
};

export async function mountSceneWorld(host: HTMLElement, options: Options, signal: AbortSignal): Promise<SceneWorld | null> {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: options.compact ? "default" : "high-performance" });
  } catch {
    return null;
  }
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.setPixelRatio(Math.min(devicePixelRatio, options.compact ? 1.5 : 2));
  renderer.setClearColor(0x050908, 1);
  renderer.domElement.setAttribute("aria-hidden", "true");

  const loader = new THREE.TextureLoader();
  const anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const urls = [...new Set(options.walls.flatMap(wall => wall.sources))];
  let loaded: THREE.Texture[];
  try {
    loaded = await Promise.all(urls.map(url => loader.loadAsync(url)));
  } catch {
    renderer.dispose();
    return null;
  }
  if (signal.aborted) { loaded.forEach(texture => texture.dispose()); renderer.dispose(); return null; }
  const textures = new Map<string, THREE.Texture>();
  loaded.forEach((texture, index) => { texture.colorSpace = THREE.NoColorSpace; texture.anisotropy = anisotropy; textures.set(urls[index], texture); });

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 1, 20000);
  const geometry = prismGeometry(), plane = new THREE.PlaneGeometry(1, 1);

  // The light field is drawn at a third of the size and becomes the scene's background.
  const fieldTarget = new THREE.WebGLRenderTarget(8, 8, { depthBuffer: false });
  const fieldMaterial = new THREE.ShaderMaterial({ vertexShader: FLAT_VERTEX, fragmentShader: FIELD_FRAGMENT, depthTest: false, depthWrite: false,
    uniforms: { uRes: { value: new THREE.Vector2(1, 1) }, uTime: { value: 0 }, uPointer: { value: new THREE.Vector2(0.5, 0.5) }, uPresence: { value: 0 }, uScroll: { value: 0 } } });
  const fieldScene = new THREE.Scene(), fieldCamera = new THREE.OrthographicCamera(-0.5, 0.5, 0.5, -0.5, 0, 1);
  fieldScene.add(new THREE.Mesh(plane, fieldMaterial));
  scene.background = fieldTarget.texture;

  let video: HTMLVideoElement | null = null, videoTexture: THREE.VideoTexture | null = null;
  const pictureOf = (wall: Wall, index: number): THREE.Texture => (wall.spec.film && videoTexture) ? videoTexture : textures.get(wall.spec.sources[index])!;
  const sizeOf = (texture: THREE.Texture): [number, number] => {
    const image = texture.image as { videoWidth?: number; videoHeight?: number; naturalWidth?: number; naturalHeight?: number; width: number; height: number };
    return [image.videoWidth || image.naturalWidth || image.width || 16, image.videoHeight || image.naturalHeight || image.height || 9];
  };
  /** The part of a picture a wall shows: centred and cropped to fill, or its left end when it glides. */
  const cover = (wall: Wall, index: number, out: THREE.Vector4, glide = 0) => {
    const [iw, ih] = sizeOf(pictureOf(wall, index));
    const frame = wall.width / Math.max(1, wall.height), image = iw / ih;
    const fx = Math.min(1, frame / image), fy = Math.min(1, image / frame);
    return out.set(fx, fy, wall.spec.glide?.includes(index) ? (1 - fx) * glide : (1 - fx) * 0.5, (1 - fy) * 0.5);
  };

  const walls: Wall[] = options.walls.map(spec => {
    const light = new THREE.ShaderMaterial({ vertexShader: FLAT_VERTEX, fragmentShader: BACKLIGHT_FRAGMENT, depthWrite: false, uniforms: { uLight: { value: 0 }, uSize: { value: new THREE.Vector2(1, 1) }, uRadius: { value: 0 } } });
    const group = new THREE.Group(), backlight = new THREE.Mesh(plane, light);
    group.add(backlight);
    group.visible = false;
    scene.add(group);
    return { spec, group, prisms: [], backlight, light, element: null, width: 0, height: 0, face: 1, current: 0, target: null, start: 0, opened: null, tiltX: 0, tiltY: 0 };
  });

  const assign = (wall: Wall) => {
    const a = pictureOf(wall, wall.current), b = wall.target === null ? a : pictureOf(wall, wall.target);
    for (const prism of wall.prisms) {
      const u = prism.material.uniforms;
      u.uTexA.value = a; u.uTexB.value = b;
      cover(wall, wall.current, u.uCoverA.value); cover(wall, wall.target ?? wall.current, u.uCoverB.value);
    }
  };
  /** Rebuild a wall for the size of its frame: about one prism for every 64 px. */
  const build = (wall: Wall, width: number, height: number) => {
    const count = Math.min(options.compact ? 16 : 26, Math.max(7, Math.round(width / (options.compact ? 46 : 64))));
    if (count !== wall.prisms.length) {
      for (const prism of wall.prisms) { wall.group.remove(prism.mesh); prism.material.dispose(); }
      wall.prisms = Array.from({ length: count }, (_, index) => {
        const material = new THREE.ShaderMaterial({ vertexShader: PRISM_VERTEX, fragmentShader: PRISM_FRAGMENT,
          uniforms: { uTexA: { value: null }, uTexB: { value: null }, uCoverA: { value: new THREE.Vector4(1, 1, 0, 0) }, uCoverB: { value: new THREE.Vector4(1, 1, 0, 0) },
            uIndex: { value: index }, uCount: { value: count }, uActivity: { value: 0 }, uFacePx: { value: 40 }, uSize: { value: new THREE.Vector2(1, 1) }, uRadius: { value: 0 },
            uLight: { value: new THREE.Vector3(-0.45, 0.35, 1) } } });
        const mesh = new THREE.Mesh(geometry, material);
        wall.group.add(mesh);
        return { mesh, material };
      });
    }
    wall.width = width; wall.height = height; wall.face = width / count;
    const radius = wall.element ? parseFloat(getComputedStyle(wall.element).borderTopLeftRadius) || 0 : 0;
    wall.prisms.forEach((prism, index) => {
      prism.mesh.position.x = -width / 2 + wall.face * (index + 0.5);
      prism.material.uniforms.uFacePx.value = wall.face;
      prism.material.uniforms.uSize.value.set(width, height);
      prism.material.uniforms.uRadius.value = radius;
    });
    wall.backlight.scale.set(width * 0.94, height * 0.94, 1);
    wall.backlight.position.z = -wall.face * 1.6;
    wall.light.uniforms.uSize.value.set(width * 0.94, height * 0.94);
    wall.light.uniforms.uRadius.value = radius;
    assign(wall);
  };

  let width = 1, height = 1, active = true, frame = 0, last = performance.now();
  const born = last;
  const pointer = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5, presence: 0, target: 0 };

  const resize = () => {
    width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    // The resting plane at z = 0 maps one to one onto the page; the lens gives the turning prisms perspective.
    camera.position.set(0, 0, height / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
    camera.far = camera.position.z * 4;
    camera.updateProjectionMatrix();
    fieldTarget.setSize(Math.max(8, Math.round(width / 3)), Math.max(8, Math.round(height / 3)));
    fieldMaterial.uniforms.uRes.value.set(width, height);
  };

  const draw = (now: number) => {
    frame = 0;
    const dt = Math.min(0.05, (now - last) / 1000), time = (now - born) / 1000;
    last = now;
    pointer.x += (pointer.tx - pointer.x) * (1 - Math.exp(-dt * 4)); pointer.y += (pointer.ty - pointer.y) * (1 - Math.exp(-dt * 4));
    pointer.presence += (pointer.target - pointer.presence) * (1 - Math.exp(-dt * 3));

    for (const wall of walls) {
      const element = wall.spec.element();
      const box = element?.getBoundingClientRect();
      if (!element || !box || box.width < 2 || box.height < 2 || box.bottom < -height * 0.5 || box.top > height * 1.5) { wall.group.visible = false; wall.element = element; continue; }
      if (element !== wall.element || Math.abs(box.width - wall.width) > 0.5 || Math.abs(box.height - wall.height) > 0.5) { wall.element = element; build(wall, box.width, box.height); }
      wall.group.visible = true;
      wall.group.position.set(box.left + box.width / 2 - width / 2, height / 2 - (box.top + box.height / 2), 0);
      // The whole wall leans a little towards the pointer; the picture itself is never cut by it.
      const lean = pointer.presence * 0.045;
      wall.tiltY += ((pointer.x - (box.left + box.width / 2) / width) * lean - wall.tiltY) * (1 - Math.exp(-dt * 5));
      wall.tiltX += ((pointer.y - (1 - (box.top + box.height / 2) / height)) * lean * 0.6 - wall.tiltX) * (1 - Math.exp(-dt * 5));
      wall.group.rotation.set(wall.tiltX, wall.tiltY, 0);

      if (wall.opened === null) wall.opened = now;
      // How far the wall has turned into its picture (with the scroll, or by itself at the top of the page),
      // and how far it has turned away again above the screen.
      const enter = wall.spec.opens ? clamp01((now - wall.opened - 250) / 1500) : clamp01((height - box.top) / (height * 0.72));
      const leave = clamp01((-box.top - box.height * 0.12) / (box.height * 0.62));
      const count = wall.prisms.length, spread = 0.7;
      const delay = wall.spec.opens ? 46 : 21, duration = 780;
      if (wall.target !== null && now - wall.start >= (count - 1) * delay + duration) { wall.current = wall.target; wall.target = null; assign(wall); }
      if (wall.spec.glide?.length) {
        const swing = 0.5 - 0.5 * Math.cos(time * 0.16);
        for (const prism of wall.prisms) { cover(wall, wall.current, prism.material.uniforms.uCoverA.value, swing); if (wall.target !== null) cover(wall, wall.target, prism.material.uniforms.uCoverB.value, swing); }
      }
      let lit = 0;
      wall.prisms.forEach((prism, index) => {
        const along = count > 1 ? index / (count - 1) : 0;
        const opened = easeTurn(clamp01(enter * (1 + spread) - spread * along));
        const closed = smooth(leave * (1 + spread) - spread * (1 - along));
        const away = Math.min(1, 1 - opened + closed);
        const progress = wall.target === null ? 0 : clamp01((now - wall.start - index * delay) / duration);
        const wave = Math.max(Math.sin(Math.PI * away), Math.sin(Math.PI * progress));
        prism.mesh.rotation.y = -TURN * away + TURN * easeTurn(progress);
        // Mid-turn each prism narrows and steps towards the viewer, opening gaps for the light behind.
        prism.mesh.scale.set(wall.face * (1 - 0.16 * wave), wall.height, wall.face * (1 - 0.16 * wave));
        prism.mesh.position.z = -APOTHEM * wall.face + wave * wall.face * 0.7;
        prism.material.uniforms.uActivity.value = Math.max(wave, away);
        lit = Math.max(lit, wave);
      });
      wall.light.uniforms.uLight.value = Math.min(1, lit * 1.6) * 1.7;
    }

    fieldMaterial.uniforms.uTime.value = time;
    fieldMaterial.uniforms.uPointer.value.set(pointer.x, pointer.y);
    fieldMaterial.uniforms.uPresence.value = pointer.presence;
    fieldMaterial.uniforms.uScroll.value = scrollY / Math.max(1, height);
    renderer.setRenderTarget(fieldTarget);
    renderer.render(fieldScene, fieldCamera);
    renderer.setRenderTarget(null);
    renderer.render(scene, camera);
    if (active) frame = requestAnimationFrame(draw);
  };
  const request = () => { if (!frame && active) { last = performance.now(); frame = requestAnimationFrame(draw); } };

  const observer = new ResizeObserver(() => { resize(); request(); });
  observer.observe(host);
  resize();
  host.appendChild(renderer.domElement);
  request();

  return {
    show(id, index) {
      const wall = walls.find(item => item.spec.id === id);
      if (!wall || index === wall.target || (index === wall.current && wall.target === null) || !wall.spec.sources[index]) return;
      if (wall.target !== null) wall.current = wall.target;
      wall.target = index; wall.start = performance.now();
      assign(wall);
      request();
    },
    film(element) {
      if (element === video) return;
      videoTexture?.dispose();
      video = element; videoTexture = null;
      if (element) { videoTexture = new THREE.VideoTexture(element); videoTexture.colorSpace = THREE.NoColorSpace; videoTexture.anisotropy = anisotropy; }
      for (const wall of walls) if (wall.spec.film && wall.prisms.length) assign(wall);
      request();
    },
    pointer(x, y, inside) { if (inside) { pointer.tx = x; pointer.ty = y; } pointer.target = inside ? 1 : 0; },
    running(value) { active = value; if (value) request(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } },
    dispose() {
      active = false;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      for (const wall of walls) { for (const prism of wall.prisms) prism.material.dispose(); wall.light.dispose(); }
      geometry.dispose(); plane.dispose(); fieldMaterial.dispose(); fieldTarget.dispose();
      textures.forEach(texture => texture.dispose()); videoTexture?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
