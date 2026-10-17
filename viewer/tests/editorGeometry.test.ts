import { describe, expect, it } from "vitest";
import {
  canvasToWorld,
  estimateSeconds,
  pathLength,
  sceneFromState,
  worldToCanvas,
  type EditorState,
} from "../src/editorGeometry";

const view = { width: 400, height: 300, mmPerPx: 0.25 }; // centre (200,150) = world origin

describe("world <-> canvas", () => {
  it("maps the origin to the canvas centre with y pointing up", () => {
    expect(worldToCanvas([0, 0], view)).toEqual([200, 150]);
    expect(worldToCanvas([10, 5], view)).toEqual([240, 130]);
  });

  it("round-trips", () => {
    const [x, y] = canvasToWorld(worldToCanvas([12.5, -7], view), view);
    expect(x).toBeCloseTo(12.5, 9);
    expect(y).toBeCloseTo(-7, 9);
  });
});

describe("pathLength", () => {
  it("sums 3D segment lengths", () => {
    expect(pathLength([[0, 0, 0], [3, 4, 0], [3, 4, 12]])).toBeCloseTo(17, 9);
  });
});

describe("sceneFromState", () => {
  it("builds the scene JSON the server expects", () => {
    const s: EditorState = {
      fly: { x: 1, y: 2, headingDeg: 90 },
      waypoints: [
        { x: 0, y: 30, z: 6 },
        { x: 0, y: 2, z: 2 },
      ],
      sizeMm: 8,
      speedMmS: 100,
      durationS: 3,
      seed: 1,
      brain: true,
    };
    expect(sceneFromState(s)).toEqual({
      duration_s: 3,
      seed: 1,
      fly: { pos: [1, 2], heading_deg: 90 },
      shadow: { size_mm: 8, speed_mm_s: 100, path: [[0, 30, 6], [0, 2, 2]] },
      environment: "tabletop",
    });
  });
});

describe("estimateSeconds", () => {
  it("uses the measured VPS cost per simulated second", () => {
    expect(estimateSeconds(3, true)).toBe(120);
    expect(estimateSeconds(3, false)).toBe(99);
  });
});
