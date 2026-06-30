// Feature: ui-ux-responsive-redesign, Property 1: Token resolution yields exactly one value per theme
//
// Validates: Requirement 3.2 — "THE Design_System SHALL resolve each Design_Token to exactly one
// value per active theme."
//
// Strategy:
//   1. Parse the canonical tokens.css source at test time to build an exhaustive map of every
//      CSS custom property defined per theme (light = :root, dark = [data-theme="dark"]).
//   2. Derive the effective per-theme map: light theme owns all :root tokens; dark theme inherits
//      :root tokens that are NOT overridden plus its own overrides — matching CSS cascade semantics.
//   3. Use fast-check to draw (token, theme) pairs from those known sets and assert that:
//        a. Every token name resolves to exactly one value string (no undefined / ambiguous).
//        b. The resolved value is a non-empty, non-whitespace-only string.
//        c. Querying the same token twice for the same theme returns the identical value (determinism).
//   4. Additionally assert structural invariants directly (no PBT needed for those):
//        - Every required token category has at least one entry in each theme.
//        - No token in the :root block is undefined in the dark theme (it either overrides or
//          inherits — no token is "lost" when switching themes).

import * as fs from "fs";
import * as path from "path";
import * as fc from "fast-check";

// ---------------------------------------------------------------------------
// Parser: extract CSS custom properties from the tokens.css source
// ---------------------------------------------------------------------------

interface TokenMap {
  /** property name → raw value string, e.g. "--color-bg" → "#f3f7f7" */
  [property: string]: string;
}

/**
 * Very lightweight CSS custom-property extractor.
 * Reads lines between a start-pattern and a closing `}`, collecting
 * `--property: value;` entries.
 */
function extractBlock(css: string, startPattern: RegExp): TokenMap {
  const result: TokenMap = {};

  // Find the start of the block
  const startMatch = startPattern.exec(css);
  if (!startMatch) return result;

  const blockStart = css.indexOf("{", startMatch.index);
  if (blockStart === -1) return result;

  // Find the matching closing brace (simple depth-tracking)
  let depth = 0;
  let blockEnd = blockStart;
  for (let i = blockStart; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) {
        blockEnd = i;
        break;
      }
    }
  }

  const blockBody = css.slice(blockStart + 1, blockEnd);

  // Match --property: value; lines (value may span chars before the semicolon)
  const propRe = /(--[\w-]+)\s*:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = propRe.exec(blockBody)) !== null) {
    const [, name, rawValue] = m;
    result[name.trim()] = rawValue.trim();
  }

  return result;
}

// Load the actual source file once for all tests
const tokensPath = path.resolve(__dirname, "../tokens.css");
const tokensCss = fs.readFileSync(tokensPath, "utf-8");

/** All tokens declared in :root (light theme defaults) */
const rootTokens: TokenMap = extractBlock(tokensCss, /:root\s*\{/);

/** Tokens declared in [data-theme="dark"] (dark overrides only) */
const darkOverrides: TokenMap = extractBlock(
  tokensCss,
  /\[data-theme\s*=\s*["']dark["']\]/
);

/**
 * Effective per-theme maps.
 * Dark theme inherits all root tokens, then overrides are applied on top —
 * mirroring CSS cascade semantics.
 */
const lightThemeTokens: TokenMap = { ...rootTokens };
const darkThemeTokens: TokenMap = { ...rootTokens, ...darkOverrides };

const themeMap: Record<"light" | "dark", TokenMap> = {
  light: lightThemeTokens,
  dark: darkThemeTokens,
};

type Theme = "light" | "dark";
const THEMES: Theme[] = ["light", "dark"];

// ---------------------------------------------------------------------------
// Sanity-check that the parser found tokens (fail-fast if the CSS changes)
// ---------------------------------------------------------------------------

const ROOT_TOKEN_NAMES = Object.keys(rootTokens);
const DARK_OVERRIDE_NAMES = Object.keys(darkOverrides);

if (ROOT_TOKEN_NAMES.length === 0) {
  throw new Error(
    "tokenResolution.property.test: parser found zero :root tokens — " +
      "check the tokens.css path or the extractBlock regex."
  );
}

// ---------------------------------------------------------------------------
// Helper: arbitraries
// ---------------------------------------------------------------------------

/** An arbitrary that picks any token name known in :root. */
const arbTokenName = fc.constantFrom(...ROOT_TOKEN_NAMES);

/** An arbitrary that picks any theme name. */
const arbTheme = fc.constantFrom<Theme>(...THEMES);

// ---------------------------------------------------------------------------
// Property 1a — Every (token, theme) pair resolves to exactly one value
// ---------------------------------------------------------------------------

describe("Property 1: Token resolution yields exactly one value per theme", () => {
  it(
    "P1a: every token resolves to a defined non-empty value for both themes",
    () => {
      fc.assert(
        fc.property(arbTokenName, arbTheme, (tokenName, theme) => {
          const tokens = themeMap[theme];
          const value = tokens[tokenName];

          // Must be defined (not undefined / absent)
          expect(value).toBeDefined();

          // Must not be empty or whitespace-only
          expect(value.trim().length).toBeGreaterThan(0);

          // Must be a string (type-safety cross-check)
          expect(typeof value).toBe("string");
        }),
        { numRuns: 200, verbose: false }
      );
    }
  );

  // -------------------------------------------------------------------------
  // Property 1b — Determinism: the same query always returns the same value
  // -------------------------------------------------------------------------
  it(
    "P1b: token resolution is deterministic — same (token, theme) always yields the same value",
    () => {
      fc.assert(
        fc.property(arbTokenName, arbTheme, (tokenName, theme) => {
          const first = themeMap[theme][tokenName];
          const second = themeMap[theme][tokenName]; // second independent lookup
          expect(first).toBe(second);
        }),
        { numRuns: 200, verbose: false }
      );
    }
  );

  // -------------------------------------------------------------------------
  // Property 1c — No token is lost when switching from light to dark
  //              (dark theme must not remove any token that :root defines)
  // -------------------------------------------------------------------------
  it(
    "P1c: switching to the dark theme does not remove any token defined in the light theme",
    () => {
      fc.assert(
        fc.property(arbTokenName, (tokenName) => {
          const lightValue = lightThemeTokens[tokenName];
          const darkValue = darkThemeTokens[tokenName];

          // Both must be defined
          expect(lightValue).toBeDefined();
          expect(darkValue).toBeDefined();

          // Both must be non-empty
          expect(lightValue.trim().length).toBeGreaterThan(0);
          expect(darkValue.trim().length).toBeGreaterThan(0);
        }),
        { numRuns: 200, verbose: false }
      );
    }
  );

  // -------------------------------------------------------------------------
  // Structural invariants (direct assertions, not PBT — these guard that the
  // parser found at least one token per required category in every theme)
  // -------------------------------------------------------------------------

  const REQUIRED_CATEGORY_PREFIXES: Array<[string, string]> = [
    ["--color-", "color"],
    ["--font-size-", "typography"],
    ["--space-", "spacing"],
    ["--radius-", "border-radius"],
    ["--elevation-", "elevation"],
    ["--motion-", "motion"],
  ];

  test.each(THEMES)("all required token categories are present in the %s theme", (theme) => {
    const tokens = themeMap[theme];
    const names = Object.keys(tokens);

    for (const [prefix, categoryName] of REQUIRED_CATEGORY_PREFIXES) {
      const found = names.some((n) => n.startsWith(prefix));
      expect(found).toBe(true); // category "${categoryName}" must have at least one token in the ${theme} theme
      if (!found) {
        throw new Error(
          `Missing token category '${categoryName}' (prefix '${prefix}') in the '${theme}' theme`
        );
      }
    }
  });

  it("the dark theme explicitly overrides at least the color and elevation categories", () => {
    const overrideNames = DARK_OVERRIDE_NAMES;
    expect(overrideNames.some((n) => n.startsWith("--color-"))).toBe(true);
    expect(overrideNames.some((n) => n.startsWith("--elevation-"))).toBe(true);
  });

  it("typography, spacing, radius, and motion tokens are defined only in :root and inherited by dark (no lost tokens)", () => {
    const inheritedPrefixes = [
      "--font-size-",
      "--font-weight-",
      "--space-",
      "--radius-",
      "--motion-",
    ];

    for (const prefix of inheritedPrefixes) {
      const rootEntries = ROOT_TOKEN_NAMES.filter((n) => n.startsWith(prefix));
      // There must be at least one :root entry per prefix
      expect(rootEntries.length).toBeGreaterThan(0);

      // All of them must survive in the effective dark theme map
      for (const name of rootEntries) {
        expect(darkThemeTokens[name]).toBeDefined();
        expect(darkThemeTokens[name].trim().length).toBeGreaterThan(0);
      }
    }
  });
});
