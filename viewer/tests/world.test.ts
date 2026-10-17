import { describe, expect, it } from "vitest";
import { flyForward, signalAt } from "../src/world";
import type { Recording } from "../src/recording";

const rec = { signals: { threat_x: [0, 10, 20] } } as unknown as Recording;

describe("signalAt", () => {
  it("interpolates between frames and clamps", () => {
    expect(signalAt(rec, "threat_x", 0.5)).toBe(5);
    expect(signalAt(rec, "threat_x", 7)).toBe(20);
  });

  it("returns null for a missing signal (no-brain runs have no threat)", () => {
    expect(signalAt(rec, "threat_y", 1)).toBeNull();
  });
});

describe("flyForward", () => {
  it("points from thorax to head in the ground plane", () => {
    const r = {
      nFrames: 1,
      partNames: ["Thorax", "Head"],
      // thorax at origin with a rotated mesh frame; head 0.7 mm along +y
      poses: new Float32Array([0, 0, 1, 0.7071, 0, 0, 0.7071, 0, 0.7, 1.2, 1, 0, 0, 0]),
    } as unknown as Recording;
    const f = flyForward(r, 0);
    expect(f.x).toBeCloseTo(0, 5);
    expect(f.y).toBeCloseTo(1, 5);
    expect(f.z).toBe(0);
  });
});
