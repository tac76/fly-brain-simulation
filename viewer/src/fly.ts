// The fly's body parts, posed from body.bin. Coordinates are MuJoCo world coordinates (mm, z up);
// the caller puts the model inside the z-up world group.
import { Group, Mesh, MeshStandardMaterial, Object3D, Quaternion, Vector3 } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { Recording } from "./recording";

const _qa = new Quaternion();
const _qb = new Quaternion();

/** Pose of one part at a fractional frame: lerp position, slerp rotation, clamped to the run. */
export function interpolatePose(
  rec: Recording,
  frameFloat: number,
  part: number,
): { position: Vector3; quaternion: Quaternion } {
  const last = rec.nFrames - 1;
  const f = Math.min(Math.max(frameFloat, 0), last);
  const f0 = Math.floor(f);
  const f1 = Math.min(f0 + 1, last);
  const t = f - f0;
  const nParts = rec.partNames.length;
  const a = (f0 * nParts + part) * 7;
  const b = (f1 * nParts + part) * 7;
  const p = rec.poses;
  const position = new Vector3(p[a], p[a + 1], p[a + 2]).lerp(
    new Vector3(p[b], p[b + 1], p[b + 2]),
    t,
  );
  // file order is (w, x, y, z); three.js is (x, y, z, w)
  _qa.set(p[a + 4], p[a + 5], p[a + 6], p[a + 3]);
  _qb.set(p[b + 4], p[b + 5], p[b + 6], p[b + 3]);
  const quaternion = _qa.clone().slerp(_qb, t).normalize();
  return { position, quaternion };
}

export class FlyModel {
  readonly root: Group;
  private parts: Object3D[] = [];
  private byName = new Map<string, Object3D>();

  constructor(source: Object3D) {
    this.root = new Group();
    this.root.name = "fly";
    source.traverse((o) => {
      if (o.name && o !== source) this.byName.set(o.name, o);
    });
  }

  /** Attach the parts named in the recording, in recording order. */
  bind(partNames: string[]): void {
    const missing = partNames.filter((n) => !this.byName.has(n));
    if (missing.length) throw new Error(`missing parts: ${missing.join(", ")}`);
    this.parts = partNames.map((n) => {
      const o = this.byName.get(n)!;
      this.root.add(o); // re-parent: world pose is set directly
      return o;
    });
  }

  part(name: string): Object3D {
    const o = this.byName.get(name);
    if (!o) throw new Error(`unknown part ${name}`);
    return o;
  }

  setPose(rec: Recording, frameFloat: number): void {
    this.parts.forEach((o, i) => {
      const { position, quaternion } = interpolatePose(rec, frameFloat, i);
      o.position.copy(position);
      o.quaternion.copy(quaternion);
    });
  }
}

export async function loadFly(url: string): Promise<FlyModel> {
  const gltf = await new GLTFLoader().loadAsync(url);
  gltf.scene.traverse((o) => {
    if (o instanceof Mesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      const old = o.material as MeshStandardMaterial;
      // vertex colours from the export; keep wings translucent
      o.material = new MeshStandardMaterial({
        vertexColors: true,
        roughness: o.name.includes("Eye") ? 0.35 : 0.6,
        metalness: 0.05,
        transparent: o.name.includes("Wing"),
        opacity: o.name.includes("Wing") ? 0.35 : 1,
        depthWrite: !o.name.includes("Wing"),
      });
      old.dispose?.();
    }
  });
  return new FlyModel(gltf.scene);
}
