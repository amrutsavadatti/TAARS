import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Vite build config — outputs a single self-contained JS bundle.
 *
 * The output is one file: dist/widget.js
 * Portfolio owners embed it with a single <script> tag.
 * React, styles, and all components are bundled inside.
 */
export default defineConfig({
  plugins: [react()],
  // Replace Node.js globals that React references internally.
  // Without this, the browser throws "process is not defined" at runtime.
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    // Output a single JS library file, not an HTML app
    lib: {
      entry: "src/index.tsx",
      name: "CareerAssistantWidget",
      fileName: "widget",
      formats: ["iife"], // IIFE = self-executing, works in any page without module system
    },
    rollupOptions: {
      // Do NOT externalise React — bundle it in so the host page
      // doesn't need to have React installed
      external: [],
      output: {
        // Single file output — everything inlined
        inlineDynamicImports: true,
      },
    },
    // Minify for production
    minify: "esbuild",
  },
  // Dev server proxies API calls to the FastAPI backend
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
