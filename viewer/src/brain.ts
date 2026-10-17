// Brain panel: every neuron of the model at its real position; spikes glow and fade.
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  Color,
  PerspectiveCamera,
  Points,
  Scene,
  ShaderMaterial,
  Vector3,
  WebGLRenderer,
} from "three";
import { frameSpikes, type Recording } from "./recording";
import type { Viewport } from "./world";

export interface BrainPoints {
  n: number;
  positions: Float32Array; // n * 3, micrometres
  groups: Uint8Array;
  groupNames: string[];
  colors: Record<string, string>;
  highlight: string[];
}

export async function loadBrainPoints(binUrl: string, jsonUrl: string): Promise<BrainPoints> {
  const [bin, meta] = await Promise.all([
    fetch(binUrl).then((r) => {
      if (!r.ok) throw new Error(`could not load ${binUrl} (HTTP ${r.status})`);
      return r.arrayBuffer();
    }),
    fetch(jsonUrl).then((r) => {
      if (!r.ok) throw new Error(`could not load ${jsonUrl} (HTTP ${r.status})`);
      return r.json();
    }),
  ]);
  const n = meta.n as number;
  return {
    n,
    positions: new Float32Array(bin, 0, n * 3),
    groups: new Uint8Array(bin, n * 12, n),
    groupNames: meta.groups,
    colors: meta.colors,
    highlight: meta.highlight,
  };
}

/** Per-neuron glow: 1 at a spike, halving every `halfLifeS` of simulated time. */
export class HeatState {
  readonly heat: Float32Array;
  private t = -1; // last fractional frame applied; -1 = nothing yet
  constructor(
    n: number,
    private halfLifeS = 0.06,
  ) {
    this.heat = new Float32Array(n);
  }

  private factor(frames: number, fps: number): number {
    return Math.pow(0.5, frames / fps / this.halfLifeS);
  }

  advanceTo(rec: Recording, frameFloat: number): Float32Array {
    const fps = rec.meta.fps || 50;
    const t1 = Math.min(Math.max(frameFloat, 0), rec.nFrames - 1);
    let from: number;
    if (t1 < this.t || this.t < 0) {
      this.heat.fill(0);
      from = 0;
    } else {
      const k = this.factor(t1 - this.t, fps);
      for (let i = 0; i < this.heat.length; i++) this.heat[i] *= k;
      from = Math.floor(this.t) + 1;
    }
    for (let s = from; s <= Math.floor(t1); s++) {
      const v = this.factor(t1 - s, fps);
      for (const i of frameSpikes(rec, s)) if (i < this.heat.length) this.heat[i] = v;
    }
    this.t = t1;
    return this.heat;
  }
}

const VERT = /* glsl */ `
attribute vec3 baseColor;
attribute float heat;
attribute float highlight;
uniform float scale;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float glow = clamp(heat, 0.0, 1.0);
  vec3 accent = mix(vec3(1.0, 0.70, 0.28), vec3(1.0, 0.95, 0.8), glow * glow);
  vColor = mix(baseColor * (0.35 + 0.5 * highlight), accent, glow);
  vAlpha = 0.16 + 0.35 * highlight + 0.84 * glow;
  gl_PointSize = scale * (1.0 + 1.6 * highlight + 3.0 * glow) / -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

const FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = dot(d, d);
  if (r > 0.25) discard;
  gl_FragColor = vec4(vColor, vAlpha * (1.0 - 4.0 * r));
}`;

export const LABELS: Record<string, string> = {
  LPLC2_L: "looming detectors (left eye)",
  LPLC2_R: "looming detectors (right eye)",
  DNp01_L: "giant fiber",
  DNa_L: "steering (DNa, left)",
  DNa_R: "steering (DNa, right)",
};

export class BrainPanel {
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(35, 1, 1, 10000);
  private heatAttr: BufferAttribute;
  private material: ShaderMaterial;
  private centroids = new Map<string, Vector3>();
  private labels = new Map<string, HTMLElement>();
  private angle = 0;
  private noBrain = false;

  constructor(
    points: BrainPoints,
    private labelLayer: HTMLElement,
  ) {
    const n = points.n;
    const geo = new BufferGeometry();
    geo.setAttribute("position", new BufferAttribute(points.positions, 3));
    const base = new Float32Array(n * 3);
    const hl = new Float32Array(n);
    const palette = points.groupNames.map((g) => new Color(points.colors[g] ?? "#555"));
    const hlIds = new Set(points.highlight.map((g) => points.groupNames.indexOf(g)));
    const sums = new Map<number, [Vector3, number]>();
    for (let i = 0; i < n; i++) {
      const g = points.groups[i];
      const c = palette[g];
      base.set([c.r, c.g, c.b], i * 3);
      if (hlIds.has(g)) {
        hl[i] = 1;
        const s = sums.get(g) ?? [new Vector3(), 0];
        s[0].add(new Vector3().fromArray(points.positions, i * 3));
        s[1] += 1;
        sums.set(g, s);
      }
    }
    for (const [g, [v, k]] of sums) this.centroids.set(points.groupNames[g], v.divideScalar(k));
    geo.setAttribute("baseColor", new BufferAttribute(base, 3));
    geo.setAttribute("highlight", new BufferAttribute(hl, 1));
    this.heatAttr = new BufferAttribute(new Float32Array(n), 1);
    geo.setAttribute("heat", this.heatAttr);
    this.material = new ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: { scale: { value: 2200 } },
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
    this.scene.add(new Points(geo, this.material));
    this.scene.background = new Color(0x05070c);
    for (const [g, text] of Object.entries(LABELS)) {
      if (!this.centroids.has(g)) continue;
      const el = document.createElement("div");
      el.className = "brain-label";
      el.textContent = text;
      labelLayer.appendChild(el);
      this.labels.set(g, el);
    }
  }

  setNoBrain(flag: boolean): void {
    this.noBrain = flag;
    this.labelLayer.dataset.noBrain = String(flag);
  }

  update(heat: Float32Array): void {
    (this.heatAttr.array as Float32Array).set(heat);
    this.heatAttr.needsUpdate = true;
  }

  render(renderer: WebGLRenderer, vp: Viewport, dtWall: number, canvasHeight: number): void {
    this.angle += dtWall * 0.12;
    const r = 1250;
    this.camera.position.set(Math.sin(this.angle) * r, 120, Math.cos(this.angle) * r);
    this.camera.lookAt(0, 0, 0);
    this.camera.aspect = vp.width / Math.max(vp.height, 1);
    this.camera.updateProjectionMatrix();
    this.material.uniforms.scale.value = vp.height * 2.2;
    renderer.setViewport(vp.x, vp.y, vp.width, vp.height);
    renderer.setScissor(vp.x, vp.y, vp.width, vp.height);
    renderer.render(this.scene, this.camera);
    for (const [g, el] of this.labels) {
      const p = this.centroids.get(g)!.clone().project(this.camera);
      const x = vp.x + ((p.x + 1) / 2) * vp.width;
      const y = canvasHeight - (vp.y + ((p.y + 1) / 2) * vp.height);
      el.style.transform = `translate(${x.toFixed(0)}px, ${y.toFixed(0)}px)`;
      el.style.display = this.noBrain ? "none" : "";
    }
  }
}
