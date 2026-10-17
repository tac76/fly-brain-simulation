// 3D world: tabletop, the fly, the looming threat and shadows. MuJoCo coordinates (mm, z up)
// live inside `zUp`, rotated so that three.js's y-up camera sees them correctly.
import {
  CanvasTexture,
  CircleGeometry,
  Color,
  DirectionalLight,
  Fog,
  Group,
  HemisphereLight,
  Mesh,
  MeshStandardMaterial,
  PCFSoftShadowMap,
  PerspectiveCamera,
  Quaternion,
  RepeatWrapping,
  Scene,
  SphereGeometry,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { FlyModel } from "./fly";
import type { Recording } from "./recording";

export interface Viewport {
  x: number;
  y: number;
  width: number;
  height: number;
}

function woodTexture(): CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 512;
  const g = c.getContext("2d")!;
  g.fillStyle = "#7a5636";
  g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 140; i++) {
    const y = Math.random() * 512;
    g.strokeStyle = `rgba(${50 + Math.random() * 30},${30 + Math.random() * 15},12,${0.04 + Math.random() * 0.06})`;
    g.lineWidth = 2 + Math.random() * 6;
    g.beginPath();
    g.moveTo(0, y);
    for (let x = 0; x <= 512; x += 32) g.lineTo(x, y + Math.sin(x / 60 + i) * 4);
    g.stroke();
  }
  const t = new CanvasTexture(c);
  t.wrapS = t.wrapT = RepeatWrapping;
  t.repeat.set(2, 2);
  t.colorSpace = SRGBColorSpace;
  return t;
}

/** Linear interpolation of a per-frame signal at a fractional frame (null if absent). */
export function signalAt(rec: Recording, name: string, frameFloat: number): number | null {
  const s = rec.signals[name];
  if (!s || s.length === 0) return null;
  const f = Math.min(Math.max(frameFloat, 0), s.length - 1);
  const f0 = Math.floor(f);
  const f1 = Math.min(f0 + 1, s.length - 1);
  return s[f0] + (s[f1] - s[f0]) * (f - f0);
}

export class World {
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(40, 1, 0.1, 2000);
  readonly controls: OrbitControls;
  private zUp = new Group();
  private threat: Mesh;
  private sun = new DirectionalLight(0xfff1dc, 2.4);
  private rec: Recording | null = null;
  private fly: FlyModel;
  private follow = false;
  private lastTarget = new Vector3();

  constructor(renderer: WebGLRenderer, fly: FlyModel) {
    this.fly = fly;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = PCFSoftShadowMap;
    this.scene.background = new Color(0x0b0f17);
    this.scene.fog = new Fog(0x0b0f17, 120, 400);
    this.zUp.rotation.x = -Math.PI / 2;
    this.scene.add(this.zUp);

    const table = new Mesh(
      new CircleGeometry(160, 96),
      new MeshStandardMaterial({ map: woodTexture(), roughness: 0.85 }),
    );
    table.receiveShadow = true;
    this.zUp.add(table);

    this.threat = new Mesh(
      new SphereGeometry(1, 48, 32),
      new MeshStandardMaterial({ color: 0x1a1a1f, roughness: 0.4, metalness: 0.1 }),
    );
    this.threat.castShadow = true;
    this.threat.visible = false;
    this.zUp.add(this.threat);

    this.zUp.add(fly.root);

    this.sun.position.set(20, 30, 120); // high sun, slightly to the side (z up)
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const cam = this.sun.shadow.camera;
    cam.left = cam.bottom = -40;
    cam.right = cam.top = 40;
    cam.near = 1;
    cam.far = 300;
    this.sun.shadow.bias = -0.0005;
    this.zUp.add(this.sun, this.sun.target);
    this.scene.add(new HemisphereLight(0xbfd4ff, 0x3b2a1a, 0.9));

    this.camera.position.set(6, 7, 11);
    this.controls = new OrbitControls(this.camera, renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.minDistance = 3;
    this.controls.maxDistance = 300;
  }

  setRecording(rec: Recording): void {
    this.rec = rec;
    this.fly.bind(rec.partNames);
    const size = rec.meta.scene?.shadow?.size_mm;
    this.threat.scale.setScalar(size ? size / 2 : 4);
    this.threat.visible = "threat_x" in rec.signals;
    this.fly.setPose(rec, 0);
    this.lastTarget.copy(this.thorax());
    this.controls.target.copy(this.lastTarget);
  }

  toggleFollow(): boolean {
    this.follow = !this.follow;
    return this.follow;
  }

  private thorax(): Vector3 {
    return this.fly.part("Thorax").getWorldPosition(new Vector3());
  }

  update(frameFloat: number): void {
    const rec = this.rec;
    if (!rec) return;
    this.fly.setPose(rec, frameFloat);
    if (this.threat.visible) {
      this.threat.position.set(
        signalAt(rec, "threat_x", frameFloat) ?? 0,
        signalAt(rec, "threat_y", frameFloat) ?? 0,
        signalAt(rec, "threat_z", frameFloat) ?? 0,
      );
    }
    const target = this.thorax();
    // keep the sun's shadow box centred on the fly (in z-up coordinates)
    const local = this.zUp.worldToLocal(target.clone());
    this.sun.target.position.copy(local);
    this.sun.position.set(local.x + 20, local.y + 30, 120);

    // camera follows the fly: shift camera and orbit target by the fly's movement
    const delta = target.clone().sub(this.lastTarget);
    this.lastTarget.copy(target);
    this.camera.position.add(delta);
    this.controls.target.add(delta);
    if (this.follow) {
      const thorax = this.fly.part("Thorax");
      const fwd = new Vector3(1, 0, 0).applyQuaternion(thorax.getWorldQuaternion(new Quaternion()));
      fwd.y = 0;
      fwd.normalize();
      const want = target.clone().addScaledVector(fwd, -14).add(new Vector3(0, 8, 0));
      this.camera.position.lerp(want, 0.08);
      this.controls.target.copy(target);
    }
    this.controls.update();
  }

  render(renderer: WebGLRenderer, vp: Viewport): void {
    this.camera.aspect = vp.width / Math.max(vp.height, 1);
    this.camera.updateProjectionMatrix();
    renderer.setViewport(vp.x, vp.y, vp.width, vp.height);
    renderer.setScissor(vp.x, vp.y, vp.width, vp.height);
    renderer.render(this.scene, this.camera);
  }
}
