import "./style.css";
import { startReplay } from "./app";
import { loadGallery, renderGallery } from "./gallery";

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
    const entries = await loadGallery();
    const run = new URLSearchParams(location.search).get("run");
    if (!run) {
      renderGallery(root, entries);
      document.body.dataset.ready = "true";
      return;
    }
    const entry = entries.find((e) => e.id === run);
    if (!entry) throw new Error(`no run called "${run}" in the gallery`);
    document.body.classList.add("replay");
    await startReplay(root, entry);
  } catch (e) {
    console.warn(e);
    showError(root, e instanceof Error ? e.message : String(e));
  }
}

void main();
