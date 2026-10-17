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

export function renderGallery(root: HTMLElement, entries: GalleryEntry[]): void {
  // static template only; manifest values are inserted below via textContent
  // static template only; manifest values are inserted below via textContent
  root.innerHTML = `
    <header class="hero">
      <h1>Fly Brain Simulation</h1>
      <p>A model of the real fruit fly brain (FlyWire connectome, ~139,000 neurons) decides how a
      physically simulated fly escapes a looming threat. Pick a recorded run.</p>
    </header>
    <main class="cards"></main>`;
  const cards = root.querySelector(".cards")!;
  for (const e of entries) {
    const a = document.createElement("a");
    a.className = "card";
    a.href = `?run=${encodeURIComponent(e.id)}`;
    a.innerHTML = `<h2></h2><p></p><span class="tag"></span>`; // static skeleton
    a.querySelector("h2")!.textContent = e.title;
    a.querySelector("p")!.textContent = e.description;
    a.querySelector(".tag")!.textContent = e.brain ? "brain model" : "no brain (baseline)";
    cards.appendChild(a);
  }
}
