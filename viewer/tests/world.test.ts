import { describe, expect, it } from "vitest";
import { signalAt } from "../src/world";
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
