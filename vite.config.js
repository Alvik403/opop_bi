import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    manifest: false,
    outDir: "static/dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "assets/src/app.js",
      output: {
        entryFileNames: "app.js",
        assetFileNames: "app.[ext]",
      },
    },
  },
});
