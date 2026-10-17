import { describe, expect, it } from "vitest";
import { statusBadges } from "../src/overlay";
import type { Recording } from "../src/recording";

function rec(meta: Record<string, unknown>, spikes: number): Recording {
  return {
    meta: { status: "complete", reason: null, warnings: [], ...meta },
    spikeIndices: new Uint32Array(spikes),
  } as unknown as Recording;
}

describe("statusBadges", () => {
  it("labels a no-brain run from the recording's brain flag", () => {
    expect(statusBadges(rec({ brain: false }, 0))).toContain("no brain in this run");
  });

  it("calls a brain run without spikes silent, not brainless", () => {
    const b = statusBadges(rec({ brain: true }, 0));
    expect(b).toContain("brain silent (no input)");
    expect(b).not.toContain("no brain in this run");
  });

  it("falls back to the gallery flag for old recordings", () => {
    expect(statusBadges(rec({}, 0), true)).toContain("brain silent (no input)");
    expect(statusBadges(rec({}, 0), false)).toContain("no brain in this run");
  });

  it("shows the abort reason", () => {
    expect(statusBadges(rec({ status: "aborted", reason: "flipped", brain: true }, 5))).toEqual([
      "aborted: flipped",
    ]);
  });
});
