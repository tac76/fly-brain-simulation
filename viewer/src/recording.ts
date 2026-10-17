// Reader for the recording format v1 (docs/recording-format.md).

export interface Meta {
  format_version: number;
  fps: number;
  n_frames: number;
  n_parts: number;
  part_names: string[];
  status: "complete" | "aborted";
  reason: string | null;
  warnings: string[];
  seed?: number;
  scene?: { shadow?: { size_mm?: number }; [key: string]: unknown };
  [key: string]: unknown;
}

export interface Recording {
  meta: Meta;
  nFrames: number;
  partNames: string[];
  poses: Float32Array; // nFrames * nParts * 7: x, y, z, qw, qx, qy, qz
  spikeOffsets: Uint32Array; // nFrames + 1
  spikeIndices: Uint32Array;
  signals: Record<string, number[]>;
}

export type Pose = [number, number, number, number, number, number, number];

export class RecordingError extends Error {}

export const FORMAT_VERSION = 1;

async function get(fetchFn: typeof fetch, url: string): Promise<Response> {
  let res: Response;
  try {
    res = await fetchFn(url);
  } catch (e) {
    throw new RecordingError(`could not load ${url}: ${String(e)}`);
  }
  if (!res.ok) throw new RecordingError(`could not load ${url} (HTTP ${res.status})`);
  return res;
}

export async function loadRecording(
  baseUrl: string,
  fetchFn: typeof fetch = fetch,
): Promise<Recording> {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  const meta = (await (await get(fetchFn, `${base}meta.json`)).json()) as Meta;
  if (meta.format_version !== FORMAT_VERSION) {
    throw new RecordingError(
      `unsupported format_version ${meta.format_version} (viewer supports ${FORMAT_VERSION})`,
    );
  }
  const [body, spikes, signals] = await Promise.all([
    get(fetchFn, `${base}body.bin`).then((r) => r.arrayBuffer()),
    get(fetchFn, `${base}spikes.bin`).then((r) => r.arrayBuffer()),
    get(fetchFn, `${base}signals.json`).then((r) => r.json() as Promise<Record<string, number[]>>),
  ]);
  const n = meta.n_frames;
  const expected = n * meta.n_parts * 7 * 4;
  if (body.byteLength !== expected) {
    throw new RecordingError(`body.bin has ${body.byteLength} bytes, expected ${expected}`);
  }
  const raw = new Uint32Array(spikes);
  return {
    meta,
    nFrames: n,
    partNames: meta.part_names,
    poses: new Float32Array(body),
    spikeOffsets: raw.subarray(0, n + 1),
    spikeIndices: raw.subarray(n + 1),
    signals,
  };
}

export function frameSpikes(rec: Recording, i: number): Uint32Array {
  return rec.spikeIndices.subarray(rec.spikeOffsets[i], rec.spikeOffsets[i + 1]);
}

export function partPose(rec: Recording, frame: number, part: number): Pose {
  const o = (frame * rec.partNames.length + part) * 7;
  return Array.from(rec.poses.subarray(o, o + 7)) as Pose;
}
