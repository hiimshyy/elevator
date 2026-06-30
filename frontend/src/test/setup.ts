import "@testing-library/jest-dom";
import { configureAxe } from "jest-axe";

// Configure jest-axe with sensible defaults
configureAxe({
  rules: {
    // Relax color-contrast for snapshot/component tests; enforced separately
  },
});
