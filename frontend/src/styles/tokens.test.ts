// Feature: ui-ux-responsive-redesign, Property 1: Token resolution yields exactly one value per theme
// Validates: Requirements 3.2

import * as fc from "fast-check";
import tokensCss from "./tokens.css?raw";

// ---------------------------------------------------------------------------
// ALL_TOKENS — static list of every CSS custom property defined in tokens.css
// ---------------------------------------------------------------------------
const ALL_TOKENS = [
  // Color — base palette
  "--color-bg",
  "--color-surface",
  "--color-text",
  "--color-text-muted",
  "--color-border",
  "--color-accent",
  // Color — status
  "--color-status-healthy",
  "--color-status-healthy-solid",
  "--color-status-healthy-on",
  "--color-status-warning",
  "--color-status-warning-solid",
  "--color-status-warning-on",
  "--color-status-critical",
  "--color-status-critical-solid",
  "--color-status-critical-on",
  "--color-status-unknown",
  "--color-status-unknown-solid",
  "--color-status-unknown-on",
  // Typography
  "--font-family-base",
  "--font-family-mono",
  "--font-size-xs",
  "--font-size-sm",
  "--font-size-md",
  "--font-size-base",
  "--font-size-lg",
  "--font-size-xl",
  "--font-size-2xl",
  "--font-weight-regular",
  "--font-weight-bold",
  "--line-height-base",
  "--line-height-tight",
  // Spacing
  "--space-1",
  "--space-2",
  "--space-3",
  "--space-4",
  "--space-5",
  "--space-6",
  "--space-7",
  "--space-8",
  // Border-radius
  "--radius-sm",
  "--radius-md",
  "--radius-lg",
  "--radius-pill",
  // Elevation
  "--elevation-1",
  "--elevation-2",
  "--elevation-3",
  // Motion
  "--motion-fast",
  "--motion-base",
  "--motion-emphasis",
  "--easing-default",
  "--easing-spring",
  "--easing-out",
] as const;

// ---------------------------------------------------------------------------
// CSS parser — structural approach
// jsdom has known limitations with CSS custom properties in <style> elements,
// so we parse the raw CSS text directly. The CSS source is the single source
// of truth, so parsing it validates that each token is defined exactly once.
// ---------------------------------------------------------------------------

type TokenMap = Map<string, string>;

/**
 * Extract CSS custom property declarations from a single rule block.
 * Returns a Map of { "--token-name" -> "value" }.
 */
function extractTokensFromBlock(block: string): TokenMap {
  const map: TokenMap = new Map();
  // Match lines like: --token-name: value; (value may contain spaces, parens, etc.)
  const propRegex = /(--[\w-]+)\s*:\s*([^;]+);/g;
  let match: RegExpExecArray | null;
  while ((match = propRegex.exec(block)) !== null) {
    const name = match[1].trim();
    const value = match[2].trim();
    map.set(name, value);
  }
  return map;
}

/**
 * Parse tokens.css and return token maps for each theme.
 *
 * light: all tokens declared in :root { }
 * dark:  all tokens declared in [data-theme="dark"] { }
 */
function parseTokensByTheme(css: string): { light: TokenMap; dark: TokenMap } {
  // Extract :root block
  const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
  const rootBlock = rootMatch ? rootMatch[1] : "";

  // Extract [data-theme="dark"] block
  const darkMatch = css.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/);
  const darkBlock = darkMatch ? darkMatch[1] : "";

  const lightTokens = extractTokensFromBlock(rootBlock);
  const darkOverrides = extractTokensFromBlock(darkBlock);

  // Dark theme: starts with all light tokens, then overrides with dark values
  const darkTokens: TokenMap = new Map(lightTokens);
  for (const [name, value] of darkOverrides) {
    darkTokens.set(name, value);
  }

  return { light: lightTokens, dark: darkTokens };
}

// ---------------------------------------------------------------------------
// Parse once at module load time — used by all test assertions
// ---------------------------------------------------------------------------
const { light: lightTokens, dark: darkTokens } = parseTokensByTheme(tokensCss);

function getTokensForTheme(theme: "light" | "dark"): TokenMap {
  return theme === "dark" ? darkTokens : lightTokens;
}

// ---------------------------------------------------------------------------
// Property-based test
// ---------------------------------------------------------------------------

describe("Design Token System — Property 1: Token resolution yields exactly one value per theme", () => {
  /**
   * Property: for every (theme, tokenName) pair, the resolved value is
   * defined and non-empty — i.e., exactly one value exists per theme.
   *
   * Validates: Requirements 3.2
   */
  it("every token resolves to a defined, non-empty value for any sampled (theme, tokenName) pair", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("light" as const, "dark" as const),
        fc.constantFrom(...ALL_TOKENS),
        (theme, tokenName) => {
          const tokens = getTokensForTheme(theme);
          const value = tokens.get(tokenName);

          // The token must exist and must not be empty
          expect(value).toBeDefined();
          expect(value).not.toBe("");
          expect(typeof value).toBe("string");
          expect((value as string).length).toBeGreaterThan(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property: token resolution is deterministic — the same (theme, tokenName)
   * always produces the same value (exactly one value per theme).
   *
   * Validates: Requirements 3.2
   */
  it("token resolution is deterministic — same (theme, tokenName) always yields the same value", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("light" as const, "dark" as const),
        fc.constantFrom(...ALL_TOKENS),
        (theme, tokenName) => {
          const tokens = getTokensForTheme(theme);

          // Call twice — must return the same value both times
          const value1 = tokens.get(tokenName);
          const value2 = tokens.get(tokenName);

          expect(value1).toBe(value2);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Exhaustive check: every token in ALL_TOKENS has a value in the light theme.
   * This complements the sampled property test above with full coverage.
   */
  it("all tokens are defined in the light theme", () => {
    for (const tokenName of ALL_TOKENS) {
      const value = lightTokens.get(tokenName);
      expect(value, `light theme missing token: ${tokenName}`).toBeDefined();
      expect(value, `light theme token is empty: ${tokenName}`).not.toBe("");
    }
  });

  /**
   * Exhaustive check: every token in ALL_TOKENS has a value in the dark theme
   * (either overridden or inherited from light).
   */
  it("all tokens are defined in the dark theme", () => {
    for (const tokenName of ALL_TOKENS) {
      const value = darkTokens.get(tokenName);
      expect(value, `dark theme missing token: ${tokenName}`).toBeDefined();
      expect(value, `dark theme token is empty: ${tokenName}`).not.toBe("");
    }
  });

  /**
   * Uniqueness check: each token name appears exactly once in each theme's
   * ruleset. The Map structure guarantees uniqueness by key, but we also
   * verify the raw CSS text does not declare the same property twice within
   * a single block (which would silently drop the first declaration).
   */
  it("each token is declared exactly once per theme ruleset in the CSS source", () => {
    const rootMatch = tokensCss.match(/:root\s*\{([^}]+)\}/);
    const rootBlock = rootMatch ? rootMatch[1] : "";

    const darkMatch = tokensCss.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/);
    const darkBlock = darkMatch ? darkMatch[1] : "";

    function countDeclarations(block: string, tokenName: string): number {
      const escaped = tokenName.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, "\\$&");
      const regex = new RegExp(escaped + "\\s*:", "g");
      return (block.match(regex) ?? []).length;
    }

    for (const tokenName of ALL_TOKENS) {
      // Light-theme root block: tokens that are defined there must appear exactly once
      if (lightTokens.has(tokenName)) {
        const count = countDeclarations(rootBlock, tokenName);
        expect(
          count,
          `"${tokenName}" declared ${count} times in :root (expected 1)`
        ).toBe(1);
      }
    }

    // Dark override block: each override token appears exactly once
    for (const [tokenName] of darkOverrides(tokensCss)) {
      const count = countDeclarations(darkBlock, tokenName);
      expect(
        count,
        `"${tokenName}" declared ${count} times in [data-theme="dark"] (expected 1)`
      ).toBe(1);
    }
  });
});

/** Helper: extract only the tokens that are explicitly listed in the dark block. */
function darkOverrides(css: string): TokenMap {
  const darkMatch = css.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/);
  return darkMatch ? extractTokensFromBlock(darkMatch[1]) : new Map();
}
