// Gallery manifest and landing page.

export interface GalleryEntry {
  id: string;
  title: string;
  description: string;
  path: string; // recording folder, relative to gallery/
  brain: boolean;
}

export async function loadGallery(url = "gallery/index.json"): Promise<GalleryEntry[]> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`could not load ${url} (HTTP ${res.status})`);
  return (await res.json()) as GalleryEntry[];
}

import { footer } from "./footer";

export function renderGallery(root: HTMLElement, entries: GalleryEntry[], editor = false): void {
  // static template only; manifest values are inserted below via textContent
  root.innerHTML = `
    <header class="hero">
      <h1>Fly Brain Simulation</h1>
      <p>A model of the real fruit fly brain (FlyWire connectome, ~139,000 neurons) decides how a
      physically simulated fly escapes a looming threat. Pick a recorded run.</p>
    </header>
    <main class="cards"></main>`;
  root.appendChild(footer());
  const cards = root.querySelector(".cards")!;
  if (editor) {
    const a = document.createElement("a");
    a.className = "card editor-card";
    a.href = "?editor";
    a.innerHTML = `<h2>Open the editor</h2><p>Place your own threat, press Apply, and watch what the
      brain does. Runs on this computer's server.</p><span class="tag">local</span>`; // static
    cards.appendChild(a);
  }
  for (const e of entries) {
    const a = document.createElement("a");
    a.className = "card";
    a.href = `?run=${encodeURIComponent(e.id)}`;
    a.innerHTML = `<img alt="" loading="lazy"><h2></h2><p></p><span class="tag"></span>`; // static
    const img = a.querySelector("img")!;
    img.src = `gallery/${e.path}thumb.jpg`;
    img.addEventListener("error", () => img.remove());
    a.querySelector("h2")!.textContent = e.title;
    a.querySelector("p")!.textContent = e.description;
    a.querySelector(".tag")!.textContent = e.brain ? "brain model" : "no brain (baseline)";
    cards.appendChild(a);
  }
}
