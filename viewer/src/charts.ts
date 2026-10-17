// Time-series charts synced to the playback cursor (uPlot).
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { Recording } from "./recording";

interface ChartSpec {
  title: string;
  series: { key: string; label: string; color: string }[];
}

const SPECS: ChartSpec[] = [
  {
    title: "Eye input (Hz per looming neuron)",
    series: [
      { key: "input_left_hz", label: "left eye", color: "#4fd1ff" },
      { key: "input_right_hz", label: "right eye", color: "#7fffd4" },
    ],
  },
  {
    title: "Brain output (Hz)",
    series: [
      { key: "gf_hz", label: "giant fiber", color: "#ffd700" },
      { key: "dna_left_hz", label: "steer L", color: "#ff6b9d" },
      { key: "dna_right_hz", label: "steer R", color: "#c77dff" },
    ],
  },
  {
    title: "Walking drive",
    series: [
      { key: "drive_left", label: "left legs", color: "#ffb347" },
      { key: "drive_right", label: "right legs", color: "#e0e0e0" },
    ],
  },
];

export class Charts {
  private plots: { plot: uPlot; cursor: HTMLElement }[] = [];

  constructor(container: HTMLElement, rec: Recording) {
    container.replaceChildren();
    const fps = rec.meta.fps || 50;
    const t = Array.from({ length: rec.nFrames }, (_, i) => (i + 1) / fps);
    const specs = SPECS.filter((s) => s.series.some((x) => x.key in rec.signals));
    for (const spec of specs) {
      const box = document.createElement("div");
      box.className = "chart";
      container.appendChild(box);
      const present = spec.series.filter((s) => s.key in rec.signals);
      const data: uPlot.AlignedData = [t, ...present.map((s) => rec.signals[s.key])];
      const plot = new uPlot(
        {
          title: spec.title,
          width: Math.max(box.clientWidth, 200),
          height: 140,
          legend: { show: true, live: false },
          cursor: { show: false },
          axes: [
            { stroke: "#8b949e", grid: { stroke: "#21262d" }, ticks: { stroke: "#30363d" } },
            { stroke: "#8b949e", grid: { stroke: "#21262d" }, ticks: { stroke: "#30363d" } },
          ],
          scales: { x: { time: false } },
          series: [
            { label: "t (s)" },
            ...present.map((s) => ({ label: s.label, stroke: s.color, width: 1.5 })),
          ],
        },
        data,
        box,
      );
      const cursor = document.createElement("div");
      cursor.className = "chart-cursor";
      plot.over.appendChild(cursor);
      this.plots.push({ plot, cursor });
    }
  }

  setTime(tS: number): void {
    for (const { plot, cursor } of this.plots) {
      cursor.style.left = `${plot.valToPos(tS, "x")}px`;
    }
  }

  resize(width: number): void {
    const w = Math.max(Math.floor(width / Math.max(this.plots.length, 1)) - 12, 200);
    for (const { plot } of this.plots) plot.setSize({ width: w, height: 140 });
  }
}
