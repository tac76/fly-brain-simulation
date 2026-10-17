// Credits shown on every page.

export function footer(): HTMLElement {
  const f = document.createElement("footer");
  f.className = "foot";
  // static, trusted markup
  f.innerHTML = `Connectome data: <a href="https://flywire.ai" target="_blank" rel="noopener">FlyWire</a>
    FAFB v783 (Dorkenwald et al. 2024; Schlegel et al. 2024), derived files under
    <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" rel="noopener">CC BY-NC 4.0</a> ·
    Brain model: Shiu et al. 2024 ·
    Body and meshes: <a href="https://github.com/NeLy-EPFL/flygym" target="_blank" rel="noopener">NeuroMechFly v2 / FlyGym</a>
    (Apache-2.0) · Code: MIT`;
  return f;
}
