import { describe, expect, it } from "vitest";
import { HeatState } from "../src/brain";
import type { Recording } from "../src/recording";

// 6 frames, neuron 1 spikes in frame 0 only, neuron 2 in frame 4
function rec(): Recording {
  const offsets = new Uint32Array([0, 1, 1, 1, 1, 2, 2]);
  return {
    meta: { fps: 50 } as Recording["meta"],
    nFrames: 6,
    partNames: [],
    poses: new Float32Array(0),
    spikeOffsets: offsets,
    spikeIndices: new Uint32Array([1, 2]),
    signals: {},
  };
}

describe("HeatState", () => {
  it("sets heat to 1 on a spike and halves it every half-life", () => {
    const h = new HeatState(4, 0.06);
    expect(h.advanceTo(rec(), 0)[1]).toBe(1);
    expect(h.advanceTo(rec(), 3)[1]).toBeCloseTo(0.5, 5); // 3 frames = 60 ms
    expect(h.advanceTo(rec(), 3)[0]).toBe(0);
  });

  it("applies spikes of every frame passed over in one jump", () => {
    const h = new HeatState(4, 0.06);
    const heat = h.advanceTo(rec(), 5);
    expect(heat[2]).toBeCloseTo(Math.pow(0.5, 1 / 3), 5); // spiked 1 frame ago
    expect(heat[1]).toBeCloseTo(Math.pow(0.5, 5 / 3), 5);
  });

  it("resets when scrubbing backwards", () => {
    const h = new HeatState(4, 0.06);
    h.advanceTo(rec(), 5);
    const heat = h.advanceTo(rec(), 2);
    expect(heat[2]).toBe(0);
    expect(heat[1]).toBeCloseTo(Math.pow(0.5, 2 / 3), 5);
  });

  it("stays zero for a recording without spikes", () => {
    const r = rec();
    r.spikeOffsets = new Uint32Array(7);
    r.spikeIndices = new Uint32Array(0);
    const heat = new HeatState(4).advanceTo(r, 5);
    expect(Array.from(heat)).toEqual([0, 0, 0, 0]);
  });
});
