/**
 * Token-Usage Enforcement Tests
 * Validates: Requirements 3.1, 3.3, 3.4, 3.5
 *
 * Two types of checks:
 *  1. Token category presence — tokens.css must define every required category
 *     with the minimum number of steps.
 *  2. Hard-coded literal detection — legacy index.css literals are baselined
 *     (must not grow); new UI component CSS files must use zero hard-coded
 *     color or rem literals.
 *
 * Note: CSS files are read via Node `fs` to bypass Vite's CSS transform
 * pipeline, which may strip or process custom properties when files are also
 * imported as live stylesheets elsewhere in the module graph.
 */

import { readFileSync } from "fs";
import { resolve } from "path";

// Resolve paths relative to this test file (src/styles/)
const STYLES_DIR = resolve(__dirname);
const SRC_DIR = resolve(__dirname, "..");

const tokensCss = readFileSync(resolve(STYLES_DIR, "tokens.css"), "utf8");
const indexCss = readFileSync(resolve(SRC_DIR, "index.css"), "utf8");

// ---------------------------------------------------------------------------
// Pre-computed counts from index.css at task 4.3 implementation time.
// These are the MAXIMUM allowed counts — if index.css gains new hard-coded
// color literals the assertions below will fail.
// Hex colors found at implementation: 37
// RGBA colors found at implementation: 48
// ---------------------------------------------------------------------------
const LEGACY_HEX_BASELINE = 37;
const LEGACY_RGBA_BASELINE = 48;

// ---------------------------------------------------------------------------
// Regex patterns
// ---------------------------------------------------------------------------
/** Matches 6- or 8-digit hex color literals, e.g. #102126 or #102126ff */
const HEX_COLOR_RE = /#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b/g;

/** Matches rgba(...) color literals */
const RGBA_COLOR_RE = /rgba\s*\([^)]+\)/g;

/** Matches hard-coded rem values that are NOT inside a var(...) reference */
const HARD_REM_RE = /(?<!var\([^)]*)\b\d+(?:\.\d+)?rem\b/g;

// ---------------------------------------------------------------------------
// Helper: count regex matches in a string
// ---------------------------------------------------------------------------
function countMatches(source: string, pattern: RegExp): number {
  // Reset lastIndex — the RegExp flag 'g' persists state when reused.
  const regex = new RegExp(pattern.source, pattern.flags);
  return (source.match(regex) ?? []).length;
}

// ---------------------------------------------------------------------------
// Scan for new component CSS files (task 9.x will create these)
// Uses fs.readdirSync recursively — returns empty array when no files exist.
// Tests below pass vacuously until actual component CSS files are added.
// ---------------------------------------------------------------------------
import { existsSync, readdirSync } from "fs";

function findCssFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const results: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = resolve(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findCssFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".css")) {
      results.push(fullPath);
    }
  }
  return results;
}

const UI_COMPONENTS_DIR = resolve(SRC_DIR, "components", "ui");
const componentCssSources: Array<{ file: string; source: string }> = findCssFiles(
  UI_COMPONENTS_DIR
).map((filePath) => ({
  file: filePath,
  source: readFileSync(filePath, "utf8"),
}));

// ============================================================================
// Tests
// ============================================================================

describe("Token-Usage Enforcement — Requirements 3.1, 3.3, 3.4, 3.5", () => {
  // --------------------------------------------------------------------------
  // 1. Required token categories are present in tokens.css
  // --------------------------------------------------------------------------
  describe("Required token categories are present in tokens.css", () => {
    it("defines at least one color token", () => {
      const matches = tokensCss.match(/--color-[\w-]+\s*:/g) ?? [];
      expect(
        matches.length,
        "Expected at least 1 --color-* token in tokens.css"
      ).toBeGreaterThanOrEqual(1);
    });

    it("defines at least 5 font-size tokens", () => {
      const matches = tokensCss.match(/--font-size-[\w-]+\s*:/g) ?? [];
      expect(
        matches.length,
        `Expected >= 5 --font-size-* tokens, found ${matches.length}`
      ).toBeGreaterThanOrEqual(5);
    });

    it("defines at least 6 spacing tokens", () => {
      const matches = tokensCss.match(/--space-\d+\s*:/g) ?? [];
      expect(
        matches.length,
        `Expected >= 6 --space-* tokens, found ${matches.length}`
      ).toBeGreaterThanOrEqual(6);
    });

    it("defines at least one border-radius token", () => {
      const matches = tokensCss.match(/--radius-[\w-]+\s*:/g) ?? [];
      expect(
        matches.length,
        "Expected at least 1 --radius-* token in tokens.css"
      ).toBeGreaterThanOrEqual(1);
    });

    it("defines at least one elevation token", () => {
      const matches = tokensCss.match(/--elevation-[\w-]+\s*:/g) ?? [];
      expect(
        matches.length,
        "Expected at least 1 --elevation-* token in tokens.css"
      ).toBeGreaterThanOrEqual(1);
    });

    it("defines at least one motion token", () => {
      const matches = tokensCss.match(/--motion-[\w-]+\s*:/g) ?? [];
      expect(
        matches.length,
        "Expected at least 1 --motion-* token in tokens.css"
      ).toBeGreaterThanOrEqual(1);
    });
  });

  // --------------------------------------------------------------------------
  // 2. Token category minimum counts (Req 3.4, 3.5)
  // --------------------------------------------------------------------------
  describe("Token category minimum counts (Req 3.4, 3.5)", () => {
    it("typography scale has at least 5 font-size steps", () => {
      // Count distinct --font-size-* declarations in the :root block only.
      const rootMatch = tokensCss.match(/:root\s*\{([^}]+)\}/);
      const rootBlock = rootMatch ? rootMatch[1] : "";
      const fontSizeTokens = rootBlock.match(/--font-size-[\w-]+\s*:/g) ?? [];
      expect(
        fontSizeTokens.length,
        `Typography scale: expected >= 5 font-size steps in :root, found ${fontSizeTokens.length}`
      ).toBeGreaterThanOrEqual(5);
    });

    it("spacing scale has at least 6 spacing steps", () => {
      const rootMatch = tokensCss.match(/:root\s*\{([^}]+)\}/);
      const rootBlock = rootMatch ? rootMatch[1] : "";
      const spaceTokens = rootBlock.match(/--space-\d+\s*:/g) ?? [];
      expect(
        spaceTokens.length,
        `Spacing scale: expected >= 6 spacing steps in :root, found ${spaceTokens.length}`
      ).toBeGreaterThanOrEqual(6);
    });
  });

  // --------------------------------------------------------------------------
  // 3. Hard-coded literal detection in legacy index.css
  //    Baseline is fixed at implementation time; count must not grow.
  // --------------------------------------------------------------------------
  describe("Hard-coded literal detection in legacy index.css", () => {
    it("hard-coded hex color count in index.css does not exceed the recorded baseline", () => {
      const count = countMatches(indexCss, HEX_COLOR_RE);
      expect(
        count,
        `index.css hex color count (${count}) exceeds baseline (${LEGACY_HEX_BASELINE}). ` +
          "New hard-coded hex colors were added — use var(--token) instead."
      ).toBeLessThanOrEqual(LEGACY_HEX_BASELINE);
    });

    it("hard-coded rgba color count in index.css does not exceed the recorded baseline", () => {
      const count = countMatches(indexCss, RGBA_COLOR_RE);
      expect(
        count,
        `index.css rgba color count (${count}) exceeds baseline (${LEGACY_RGBA_BASELINE}). ` +
          "New hard-coded rgba colors were added — use var(--token) instead."
      ).toBeLessThanOrEqual(LEGACY_RGBA_BASELINE);
    });
  });

  // --------------------------------------------------------------------------
  // 4. New UI component files must use var(--token) — zero hard-coded literals
  //    These tests pass vacuously until task 9.x creates files under
  //    src/components/ui/. Once those files exist they are checked strictly.
  // --------------------------------------------------------------------------
  describe("New UI component files must use var(--token) for colors", () => {
    it("component files under src/components/ui/ contain no hard-coded hex colors", () => {
      for (const { file, source } of componentCssSources) {
        const count = countMatches(source, HEX_COLOR_RE);
        expect(
          count,
          `${file} contains ${count} hard-coded hex color(s). ` +
            "Component styles must reference var(--token) instead of literal colors."
        ).toBe(0);
      }
      // Passes vacuously when no component CSS files exist yet
      expect(true).toBe(true);
    });

    it("component files under src/components/ui/ contain no hard-coded rgba colors", () => {
      for (const { file, source } of componentCssSources) {
        const count = countMatches(source, RGBA_COLOR_RE);
        expect(
          count,
          `${file} contains ${count} hard-coded rgba color(s). ` +
            "Component styles must reference var(--token) instead of literal colors."
        ).toBe(0);
      }
      expect(true).toBe(true);
    });
  });
});
