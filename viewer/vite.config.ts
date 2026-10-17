import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  // `npm run dev` talks to a running `flybrain serve` for the editor
  server: { proxy: { "/api": "http://127.0.0.1:8770" } },
  preview: { proxy: {} }, // `vite preview` behaves like a static host (GitHub Pages)
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
} as never);
