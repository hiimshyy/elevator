// Feature: ui-ux-responsive-redesign, Property 16: For all selectable themes, persisting the theme and then resolving the initial theme (with persistence succeeding and the operating-system scheme held fixed) returns the same theme that was persisted.
//
// Validates: Requirements 8.6
//
// Property 16 (from design.md):
//   For all selectable themes, persisting the theme and then resolving the
//   initial theme (with persistence succeeding and the operating-system
//   scheme held fixed) returns the same theme that was persisted.
//
// Strategy:
//   1. Use fast-check to draw a theme from the selectable set {"light", "dark"}
//      (the only themes provided by Requirement 8.1) together with a fixed OS
//      scheme drawn from {"light", "dark", "indeterminate"}. The OS scheme is
//      held fixed within each iteration; varying it across iterations confirms
//      the round-trip is independent of the OS preference because a stored
//      preference takes precedence (Requirement 8.4).
//   2. Persist the theme to localStorage under the documented key
//      `elevator-pdm.theme`, simulating that the persistence step in
//      `setTheme` succeeded (Requirement 8.6).
//   3. Replace `window.matchMedia` with a deterministic stub matching the
//      drawn OS scheme so the resolver runs in a known environment.
//   4. Invoke `resolveInitialTheme()` and assert the returned theme equals
//      the persisted value, and that the resolver reports `source === "stored"`
//      (i.e. the round-trip actually traversed the persistence path rather
//      than coincidentally agreeing through the OS or default branches).
//   5. Run a minimum of 100 iterations via fast-check.

import * as fc from "fast-check";
import { resolveInitialTheme, THEME_STORAGE_KEY, type ThemeName } from "../ThemeProvider";

// ---------------------------------------------------------------------------
// Input domains
// ---------------------------------------------------------------------------

/** Selectable themes per Requirement 8.1. */
const SELECTABLE_THEMES: ThemeName[] = ["light", "dark"];

/** OS color-scheme values the resolver must tolerate. */
type SystemScheme = "light" | "dark" | "indeterminate";
const SYSTEM_VALUES: SystemScheme[] = ["light", "dark", "indeterminate"];

// ---------------------------------------------------------------------------
// Environment stubs
// ---------------------------------------------------------------------------

/**
 * Replace `window.matchMedia` with a deterministic stub that mirrors the
 * supplied OS color-scheme. jsdom does not implement matchMedia natively,
 * so we install a fresh implementation each iteration to avoid carry-over.
 */
function stubMatchMedia(scheme: SystemScheme): void {
  const matcher = (query: string): MediaQueryList => {
    const normalized = query.replace(/\s+/g, " ").trim();
    const matchesDark =
      scheme === "dark" && normalized === "(prefers-color-scheme: dark)";
    const matchesLight =
      scheme === "light" && normalized === "(prefers-color-scheme: light)";

    return {
      matches: matchesDark || matchesLight,
      media: normalized,
      onchange: null,
      // legacy listener API (older WebKit)
      addListener: () => {},
      removeListener: () => {},
      // modern EventTarget API
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false
    } as unknown as MediaQueryList;
  };

  (window as unknown as { matchMedia: typeof window.matchMedia }).matchMedia =
    matcher as typeof window.matchMedia;
}

/**
 * Persist the theme exactly as `setTheme` does on the success path. This
 * isolates the property from the React component and exercises the contract
 * between the persistence step and the resolver directly.
 */
function persistTheme(theme: ThemeName): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, theme);
}

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 16: Theme persistence round-trips", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("16: persisting a selectable theme and then resolving returns the same theme", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<ThemeName>(...SELECTABLE_THEMES),
        fc.constantFrom<SystemScheme>(...SYSTEM_VALUES),
        (persisted, system) => {
          // Reset cross-iteration state so each round-trip is independent.
          window.localStorage.clear();
          stubMatchMedia(system);

          // Step 1: persist the theme (simulating setTheme's success path).
          persistTheme(persisted);

          // Step 2: resolve the initial theme as if the app were reloaded.
          const result = resolveInitialTheme();

          // Step 3: the round-trip must return the same theme.
          expect(result.theme).toBe(persisted);

          // The resolved source must be "stored", confirming the resolver
          // traversed the persistence branch rather than the OS or default
          // branch (strengthens the property beyond coincidental equality).
          expect(result.source).toBe("stored");
        }
      ),
      { numRuns: 100 }
    );
  });

  // -------------------------------------------------------------------------
  // Exhaustive sanity check — the full 2×3 grid is covered explicitly so a
  // shrunken fast-check counter-example always has a named partner here.
  // -------------------------------------------------------------------------
  it("covers all (selectable-theme × OS-scheme) combinations exhaustively", () => {
    for (const persisted of SELECTABLE_THEMES) {
      for (const system of SYSTEM_VALUES) {
        window.localStorage.clear();
        stubMatchMedia(system);
        persistTheme(persisted);

        const result = resolveInitialTheme();

        expect(result.theme).toBe(persisted);
        expect(result.source).toBe("stored");
      }
    }
  });
});
