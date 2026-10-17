import "./style.css";
import { startReplay } from "./app";
import { startEditor } from "./editor";
import { loadGallery, renderGallery } from "./gallery";

/** Served by `flybrain serve`? (the server marks index.html; static hosts do not) */
function servedByEditor(): boolean {
  return document.querySelector('meta[name="flybrain-server"]') !== null;
}

async function serverPresent(): Promise<boolean> {
  try {
    const r = await fetch("api/health");
    return r.ok && (await r.json()).editor === true;
  } catch {
    return false;
  }
}

function showError(root: HTMLElement, message: string): void {
  root.replaceChildren();
  const box = document.createElement("div");
  box.className = "error";
  const h = document.createElement("h2");
  h.textContent = "Could not load this run";
  const p = document.createElement("p");
  p.textContent = message;
  const a = document.createElement("a");
  a.href = "./";
  a.textContent = "← back to all runs";
  box.append(h, p, a);
  root.appendChild(box);
  document.body.dataset.error = "true";
}

async function main(): Promise<void> {
  const root = document.querySelector<HTMLElement>("#app")!;
  try {
    const params = new URLSearchParams(location.search);
    if (params.has("editor")) {
      if (!(await serverPresent())) {
        throw new Error("the editor needs the local server: run `flybrain serve`");
      }
      document.body.classList.add("editor-page");
      startEditor(root);
      return;
    }
    const rec = params.get("rec");
    if (rec) {
      document.body.classList.add("replay");
      const brain = params.get("brain");
      await startReplay(root, {
        title: params.get("title") ?? "Recording",
        url: rec,
        brain: brain === null ? undefined : brain === "1",
      });
      return;
    }
    const entries = await loadGallery();
    const run = params.get("run");
    if (!run) {
      renderGallery(root, entries, servedByEditor());
      document.body.dataset.ready = "true";
      return;
    }
    const entry = entries.find((e) => e.id === run);
    if (!entry) throw new Error(`no run called "${run}" in the gallery`);
    document.body.classList.add("replay");
    await startReplay(root, { title: entry.title, url: `gallery/${entry.path}`, brain: entry.brain });
  } catch (e) {
    console.warn(e);
    showError(root, e instanceof Error ? e.message : String(e));
  }
}

void main();
