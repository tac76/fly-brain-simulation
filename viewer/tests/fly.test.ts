import { describe, expect, it } from "vitest";
import { Group, Object3D } from "three";
import { FlyModel, interpolatePose } from "../src/fly";
import type { Recording } from "../src/recording";

function rec(frames: number[][][]): Recording {
  // frames[f][part] = pose (7 numbers)
  const nParts = frames[0].length;
  return {
    meta: {} as Recording["meta"],
    nFrames: frames.length,
    partNames: Array.from({ length: nParts }, (_, i) => `P${i}`),
    poses: new Float32Array(frames.flat(2)),
    spikeOffsets: new Uint32Array(frames.length + 1),
    spikeIndices: new Uint32Array(0),
    signals: {},
  };
}

function groupWith(names: string[]): Group {
  const g = new Group();
  const inner = new Group(); // GLB loaders nest nodes under a root
  for (const n of names) {
    const o = new Object3D();
    o.name = n;
    inner.add(o);
  }
  g.add(inner);
  return g;
}

describe("FlyModel", () => {
  it("bind throws listing missing parts", () => {
    const model = new FlyModel(groupWith(["P0"]));
    expect(() => model.bind(["P0", "P1", "P2"])).toThrow("missing parts: P1, P2");
  });

  it("setPose places parts from the recording", () => {
    const model = new FlyModel(groupWith(["P0", "P1"]));
    model.bind(["P0", "P1"]);
    const r = rec([[[0, 0, 0, 1, 0, 0, 0], [5, 0, 0, 1, 0, 0, 0]]]);
    model.setPose(r, 0);
    expect(model.part("P1").position.x).toBe(5);
  });
});

describe("interpolatePose", () => {
  it("returns the midpoint and a unit quaternion at frame 1.5", () => {
    const s = Math.SQRT1_2;
    const r = rec([[[0, 0, 0, 1, 0, 0, 0]], [[2, 0, 0, 1, 0, 0, 0]], [[4, 2, 0, s, 0, 0, s]]]);
    const { position, quaternion } = interpolatePose(r, 1.5, 0);
    expect(position.toArray()).toEqual([3, 1, 0]);
    expect(quaternion.length()).toBeCloseTo(1, 6);
    // halfway between identity and 90 deg about z: 45 deg
    expect(2 * Math.acos(quaternion.w)).toBeCloseTo(Math.PI / 4, 5);
  });

  it("clamps outside the recording", () => {
    const r = rec([[[1, 0, 0, 1, 0, 0, 0]], [[2, 0, 0, 1, 0, 0, 0]]]);
    expect(interpolatePose(r, 9, 0).position.x).toBe(2);
    expect(interpolatePose(r, -1, 0).position.x).toBe(1);
  });
});
