import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    // By default Vitest stubs every `.css` import (including `?raw` queries),
    // which makes `import tokensCss from "./tokens.css?raw"` resolve to an
    // empty string. tokens.css is the single source of truth for our design
    // tokens (parsed by `src/a11y/contrast.ts` and the property tests), so
    // we whitelist it for normal Vite processing here. Other CSS imports
    // remain stubbed.
    css: {
      include: [/tokens\.css/],
    },
  },
});
