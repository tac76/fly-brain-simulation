// "How it works" panel and status badges.
import type { Recording } from "./recording";

export const HOW_IT_WORKS = `
<h3>How it works</h3>
<p>Every 20 ms of simulated time:</p>
<ol>
  <li><b>Eyes (hand-built encoding):</b> how large and how fast-growing the threat looks to each
  eye becomes input to the brain's looming-detector neurons (LPLC2, LC4).</li>
  <li><b>Brain (the model):</b> all ~139,000 neurons of the FlyWire connectome are simulated as
  spiking neurons (Shiu et al. 2024). Nothing in this step is hand-written behaviour.</li>
  <li><b>Read-out:</b> descending neurons that steer (DNa01/DNa02) and trigger escape
  (giant fiber, DNp01).</li>
  <li><b>Motor mapping (hand-built):</b> left-vs-right steering activity becomes a turn, giant
  fiber activity a speed-up.</li>
  <li><b>Body (physics):</b> a physically simulated fly (NeuroMechFly / FlyGym, MuJoCo). Its legs
  are moved by a built-in gait controller.</li>
</ol>
<p><b>Walking itself is a default:</b> with a silent brain the fly walks straight. Turning away
and speeding up come from the brain model's output.</p>
<p class="small">Data: FlyWire (CC BY-NC 4.0). Model: Shiu et al. 2024. Body: NeuroMechFly v2.</p>`;

/** Whether a brain model ran: the recording's own flag, else the gallery entry's. */
export function hasBrain(rec: Recording, galleryFlag?: boolean): boolean {
  const flag = rec.meta.brain;
  return typeof flag === "boolean" ? flag : (galleryFlag ?? rec.spikeIndices.length > 0);
}

export function statusBadges(rec: Recording, galleryFlag?: boolean): string[] {
  const out: string[] = [];
  if (rec.meta.status === "aborted") out.push(`aborted: ${rec.meta.reason ?? "unknown"}`);
  for (const w of rec.meta.warnings ?? []) out.push(`warning: ${w.replace(/_/g, " ")}`);
  if (!hasBrain(rec, galleryFlag)) out.push("no brain in this run");
  else if (rec.spikeIndices.length === 0) out.push("brain silent (no input)");
  return out;
}
