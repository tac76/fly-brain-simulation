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
  vColor = mix(baseColor * (0.8 + 0.6 * highlight), accent, glow);
  vAlpha = 0.28 + 0.5 * highlight + 0.72 * glow;
  gl_PointSize = scale * (1.0 + 1.5 * highlight + 3.5 * glow) / -mv.z;
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

// label text and pixel offset from the group's centroid (keeps labels from overlapping)
export const LABELS: Record<string, [string, number, number]> = {
  LPLC2_L: ["looming input L", -150, -48],
  LPLC2_R: ["looming input R", 40, -48],
  DNp01_L: ["giant fiber", -150, 30],
  DNa_L: ["steering L", -150, 60],
  DNa_R: ["steering R", 40, 60],
};

export class BrainPanel {
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(35, 1, 1, 10000);
  private heatAttr: BufferAttribute;
  private material: ShaderMaterial;
  private centroids = new Map<string, Vector3>();
  private labels = new Map<string, { el: HTMLElement; dot: HTMLElement; dx: number; dy: number }>();
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
    for (const [g, [text, dx, dy]] of Object.entries(LABELS)) {
      if (!this.centroids.has(g)) continue;
      const el = document.createElement("div");
      el.className = "brain-label";
      el.textContent = text;
      const dot = document.createElement("div");
      dot.className = "brain-dot";
      labelLayer.append(el, dot);
      this.labels.set(g, { el, dot, dx, dy });
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

  render(renderer: WebGLRenderer, vp: Viewport, dtWall: number): void {
    // gentle back-and-forth sway around the frontal view keeps the brain readable
    this.angle += dtWall * 0.25;
    const yaw = Math.sin(this.angle) * 0.6;
    const r = 820;
    this.camera.position.set(Math.sin(yaw) * r, 160, Math.cos(yaw) * r);
    this.camera.lookAt(0, 0, 0);
    this.camera.aspect = vp.width / Math.max(vp.height, 1);
    this.camera.updateProjectionMatrix();
    this.material.uniforms.scale.value = vp.height * 3.0;
    renderer.setViewport(vp.x, vp.y, vp.width, vp.height);
    renderer.setScissor(vp.x, vp.y, vp.width, vp.height);
    renderer.render(this.scene, this.camera);
    const scale = Math.min(vp.width / 520, 1);
    for (const [g, { el, dot, dx, dy }] of this.labels) {
      const p = this.centroids.get(g)!.clone().project(this.camera);
      const x = ((p.x + 1) / 2) * vp.width;
      const y = ((1 - p.y) / 2) * vp.height;
      dot.style.transform = `translate(${x.toFixed(0)}px, ${y.toFixed(0)}px)`;
      // keep labels inside the panel
      const lx = Math.min(Math.max(x + dx * scale, 4), vp.width - el.offsetWidth - 4);
      const ly = Math.min(Math.max(y + dy, 24), vp.height - el.offsetHeight - 4);
      el.style.transform = `translate(${lx.toFixed(0)}px, ${ly.toFixed(0)}px)`;
      el.style.display = dot.style.display = this.noBrain ? "none" : "";
    }
  }
}
