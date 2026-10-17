import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { frameSpikes, loadRecording, partPose, RecordingError } from "../src/recording";

const FIX = new URL("./fixtures/", import.meta.url);

// fetch replacement serving files from the fixtures folder (optionally overriding one file)
function fsFetch(overrides: Record<string, string> = {}): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = String(input);
    const name = url.split("/").pop() ?? "";
    if (name in overrides) return new Response(overrides[name]);
    try {
      const data = await readFile(new URL(url, FIX));
      return new Response(data);
    } catch {
      return new Response("not found", { status: 404 });
    }
  }) as typeof fetch;
}

describe("loadRecording", () => {
  it("reads the tiny fixture written by Python", async () => {
    const rec = await loadRecording("tiny/", fsFetch());
    expect(rec.nFrames).toBe(3);
    expect(rec.partNames).toEqual(["A", "B"]);
    expect(Array.from(frameSpikes(rec, 2))).toEqual([2, 102]);
    expect(partPose(rec, 2, 1)).toEqual([2, 12, 0, 1, 0, 0, 0]);
    expect(rec.signals.gf_hz).toEqual([0, 50, 100]);
  });

  it("reads an aborted recording", async () => {
    const rec = await loadRecording("aborted/", fsFetch());
    expect(rec.meta.status).toBe("aborted");
    expect(rec.meta.reason).toBe("flipped");
    expect(rec.nFrames).toBe(1);
    expect(frameSpikes(rec, 0).length).toBe(0);
  });

  it("rejects an unknown format version", async () => {
    const meta = JSON.parse(await readFile(new URL("tiny/meta.json", FIX), "utf8"));
    meta.format_version = 99;
    await expect(
      loadRecording("tiny/", fsFetch({ "meta.json": JSON.stringify(meta) })),
    ).rejects.toThrow(/format_version/);
  });

  it("names the missing file on 404", async () => {
    const err = await loadRecording("missing/", fsFetch()).catch((e) => e);
    expect(err).toBeInstanceOf(RecordingError);
    expect(String(err.message)).toMatch(/meta\.json/);
  });
});
