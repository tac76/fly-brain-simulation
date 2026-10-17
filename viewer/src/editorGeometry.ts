// Pure helpers for the scene editor (top-down view of the arena, scene JSON).

export interface View {
  width: number;
  height: number;
  mmPerPx: number;
}

export interface Waypoint {
  x: number;
  y: number;
  z: number;
}

export interface EditorState {
  fly: { x: number; y: number; headingDeg: number };
  waypoints: Waypoint[];
  sizeMm: number;
  speedMmS: number;
  durationS: number;
  seed: number;
  brain: boolean;
}

export const ARENA_RADIUS_MM = 60;
export const MAX_WAYPOINTS = 4;
// measured on the VPS (one CPU core): brain + body ~40 s, body only ~33 s per simulated second
const COST_BRAIN = 40;
const COST_BODY = 33;

/** World mm (x right, y up) -> canvas px (y down), origin at the canvas centre. */
export function worldToCanvas([x, y]: [number, number], v: View): [number, number] {
  return [v.width / 2 + x / v.mmPerPx, v.height / 2 - y / v.mmPerPx];
}

export function canvasToWorld([px, py]: [number, number], v: View): [number, number] {
  return [(px - v.width / 2) * v.mmPerPx, (v.height / 2 - py) * v.mmPerPx];
}

export function pathLength(path: [number, number, number][]): number {
  let total = 0;
  for (let i = 1; i < path.length; i++) {
    const [a, b] = [path[i - 1], path[i]];
    total += Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  }
  return total;
}

const r2 = (v: number) => Math.round(v * 100) / 100;

export function sceneFromState(s: EditorState): Record<string, unknown> {
  return {
    duration_s: s.durationS,
    seed: s.seed,
    fly: { pos: [r2(s.fly.x), r2(s.fly.y)], heading_deg: r2(s.fly.headingDeg) },
    shadow: {
      size_mm: s.sizeMm,
      speed_mm_s: s.speedMmS,
      path: s.waypoints.map((w) => [r2(w.x), r2(w.y), r2(w.z)]),
    },
    environment: "tabletop",
  };
}

export function estimateSeconds(durationS: number, brain: boolean): number {
  return Math.round(durationS * (brain ? COST_BRAIN : COST_BODY));
}

/** Presets: threat diving at a fly at the origin facing +x (heading 0). */
export function preset(name: "left" | "right" | "front"): Waypoint[] {
  if (name === "left") return [{ x: 0, y: 30, z: 6 }, { x: 0, y: 2, z: 2 }];
  if (name === "right") return [{ x: 0, y: -30, z: 6 }, { x: 0, y: -2, z: 2 }];
  return [{ x: 30, y: 0, z: 6 }, { x: 3, y: 0, z: 2 }];
}
