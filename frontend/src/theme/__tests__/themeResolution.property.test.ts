// Feature: ui-ux-responsive-redesign, Property 15: Theme resolution follows stored-then-system-then-default precedence
//
// Validates: Requirements 8.2, 8.3, 8.4
//
// Property 15 (from design.md):
//   For all combinations of stored preference (none, "light", "dark") and
//   operating-system color-scheme (light, dark, indeterminate), the resolved
//   theme returned by `resolveInitialTheme()` is:
//     - the stored preference when one exists                    (Req 8.4);
//     - otherwise the OS color-scheme when it is light or dark   (Req 8.2);
//     - otherwise the light theme                                (Req 8.3).
//
// Strategy:
//   1. Use fast-check to draw (stored, system) pairs from the full cartesian
//      product {none, "light", "dark"} × {"light", "dark", "indeterminate"}.
//   2. Before each iteration, reset localStorage and replace `window.matchMedia`
//      with a deterministic stub that reflects the drawn OS color-scheme.
//   3. Invoke `resolveInitialTheme()` and assert both the resolved theme and
//      the reported source match the documented precedence chain.
//   4. Run at least 100 iterations (fast-check default), with the generators
//      constrained to the 9 valid combinations.

import * as fc from "fast-check";
import { resolveInitialTheme, THEME_STORAGE_KEY } from "../ThemeProvider";

// ---------------------------------------------------------------------------
// Input domains
// ---------------------------------------------------------------------------

type StoredPreference = "none" | "light" | "dark";
type SystemScheme = "light" | "dark" | "indeterminate";

const STORED_VALUES: StoredPreference[] = ["none", "light", "dark"];
const SYSTEM_VALUES: SystemScheme[] = ["light", "dark", "indeterminate"];

// ---------------------------------------------------------------------------
// Environment stubs
// ---------------------------------------------------------------------------

/**
 * Replace `window.matchMedia` with a deterministic stub that mirrors the
 * supplied OS color-scheme. jsdom does not implement matchMedia natively, so
 * we install a fresh implementation each iteration to avoid carry-over.
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

  // Assigning directly is sufficient under jsdom; vi.stubGlobal would also work
  // but a plain assignment keeps the stub local to this test file.
  (window as unknown as { matchMedia: typeof window.matchMedia }).matchMedia =
    matcher as typeof window.matchMedia;
}

/** Reset and optionally seed the persisted theme preference. */
function seedStoredPreference(stored: StoredPreference): void {
  window.localStorage.removeItem(THEME_STORAGE_KEY);
  if (stored !== "none") {
    window.localStorage.setItem(THEME_STORAGE_KEY, stored);
  }
}

/** Compute the expected (theme, source) per the documented precedence chain. */
function expectedResolution(
  stored: StoredPreference,
  system: SystemScheme
): { theme: "light" | "dark"; source: "stored" | "system" | "default" } {
  if (stored !== "none") {
    return { theme: stored, source: "stored" };
  }
  if (system === "light" || system === "dark") {
    return { theme: system, source: "system" };
  }
  return { theme: "light", source: "default" };
}

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 15: Theme resolution follows stored-then-system-then-default precedence", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("15: resolveInitialTheme honors stored > OS > light-default for every combination", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<StoredPreference>(...STORED_VALUES),
        fc.constantFrom<SystemScheme>(...SYSTEM_VALUES),
        (stored, system) => {
          // Reset and prepare environment for this iteration.
          window.localStorage.clear();
          seedStoredPreference(stored);
          stubMatchMedia(system);

          const result = resolveInitialTheme();
          const expected = expectedResolution(stored, system);

          // Theme correctness — direct expression of Requirements 8.2, 8.3, 8.4.
          expect(result.theme).toBe(expected.theme);

          // Source correctness — strengthens the property by verifying the
          // precedence chain actually branched as documented (not coincidence).
          expect(result.source).toBe(expected.source);
        }
      ),
      { numRuns: 100 }
    );
  });

  // -------------------------------------------------------------------------
  // Exhaustive sanity check — the full 3×3 grid is covered explicitly so a
  // shrunken fast-check counter-example always has a named partner here.
  // -------------------------------------------------------------------------
  it("covers all 9 (stored × system) combinations exhaustively", () => {
    for (const stored of STORED_VALUES) {
      for (const system of SYSTEM_VALUES) {
        window.localStorage.clear();
        seedStoredPreference(stored);
        stubMatchMedia(system);

        const result = resolveInitialTheme();
        const expected = expectedResolution(stored, system);

        expect(result.theme).toBe(expected.theme);
        expect(result.source).toBe(expected.source);
      }
    }
  });
});
