import { describe, expect, it } from "vitest";
import { Playback } from "../src/playback";

describe("Playback", () => {
  it("advances fps x speed x dt frames while playing", () => {
    const p = new Playback(150, 50);
    p.playing = true;
    p.speed = 0.5;
    expect(p.tick(0.2)).toBeCloseTo(5); // 50 * 0.5 * 0.2
  });

  it("does not move while paused", () => {
    const p = new Playback(150, 50);
    expect(p.tick(1)).toBe(0);
  });

  it("clamps at the end and stops", () => {
    const p = new Playback(10, 50);
    p.playing = true;
    expect(p.tick(5)).toBe(9);
    expect(p.playing).toBe(false);
  });

  it("seek clamps to the recording", () => {
    const p = new Playback(10, 50);
    p.seek(99);
    expect(p.frame).toBe(9);
    p.seek(-3);
    expect(p.frame).toBe(0);
  });

  it("play at the end restarts from the beginning", () => {
    const p = new Playback(10, 50);
    p.seek(9);
    p.play();
    expect(p.frame).toBe(0);
    expect(p.playing).toBe(true);
  });
});
