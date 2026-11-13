"use client";

import { useEffect, useRef } from "react";
import lp from "./optical-landing.module.css";

/** Light through glass on a white bench: a slow WebGL gradient behind the mission statement, in the lab
 *  white of the hero film with the warm colour of culture medium. The CSS gradient under it stands in
 *  when motion is reduced or WebGL is unavailable, and the field stops while it is off screen. */
const FRAGMENT = `#version 300 es
precision highp float;uniform vec2 res;uniform float time;out vec4 color;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
void main(){
  vec2 uv=gl_FragCoord.xy/res;vec2 p=uv*vec2(res.x/res.y,1.);float t=time*.035;
  float flow=fbm(p*1.25+vec2(t,-t*.6));float fine=fbm(p*3.2+flow*1.6-vec2(t*1.4,0.));
  vec3 c=mix(vec3(.925,.937,.927),vec3(.972,.975,.966),smoothstep(0.,1.,uv.y*.8+flow*.35));
  vec2 m=uv-vec2(.8+.04*sin(time*.05),.24+.05*cos(time*.04));
  c=mix(c,vec3(.94,.76,.68),exp(-dot(m*vec2(1.,1.5),m*vec2(1.,1.5))*6.)*(.42+.25*fine));
  float sheen=pow(.5+.5*sin((p.x*.7+p.y*.45)*2.4+flow*2.2+time*.05),3.);
  c+=vec3(1.,.99,.97)*sheen*smoothstep(.3,.95,uv.x)*.05;
  c=mix(c,vec3(.83,.9,.88),smoothstep(.62,.95,fine)*.16*smoothstep(.3,1.,uv.x));
  c+=(hash(gl_FragCoord.xy+time)-.5)*.014;
  color=vec4(c,1.);}`;
const VERTEX = `#version 300 es
in vec2 position;void main(){gl_Position=vec4(position,0.,1.);}`;

export function LightField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const gl = canvas.getContext("webgl2", { antialias: false, alpha: false, premultipliedAlpha: false });
    if (!gl) return;
    const compile = (type: number, source: string) => { const shader = gl.createShader(type)!; gl.shaderSource(shader, source); gl.compileShader(shader); return shader; };
    const program = gl.createProgram()!;
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const res = gl.getUniformLocation(program, "res"), time = gl.getUniformLocation(program, "time");
    // Half resolution: the field is soft, and it keeps the GPU quiet.
    const scale = Math.min(devicePixelRatio, 2) * 0.5;
    const resize = () => { canvas.width = Math.max(1, Math.round(canvas.clientWidth * scale)); canvas.height = Math.max(1, Math.round(canvas.clientHeight * scale)); gl.viewport(0, 0, canvas.width, canvas.height); };
    let frame = 0, visible = false;
    const start = performance.now();
    const draw = () => {
      frame = 0;
      if (!visible) return;
      gl.uniform2f(res, canvas.width, canvas.height);
      gl.uniform1f(time, (performance.now() - start) / 1000 + 40);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.dataset.state = "ready";
      frame = requestAnimationFrame(draw);
    };
    const sizes = new ResizeObserver(resize);
    sizes.observe(canvas);
    const seen = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible && !frame) frame = requestAnimationFrame(draw); });
    seen.observe(canvas);
    resize();
    return () => { cancelAnimationFrame(frame); sizes.disconnect(); seen.disconnect(); gl.deleteBuffer(buffer); gl.deleteProgram(program); };
  }, []);
  return <canvas ref={ref} className={lp.lightField} aria-hidden="true" />;
}
