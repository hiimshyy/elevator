// Feature: ui-ux-responsive-redesign, Property 6: Palette contrast meets WCAG AA in every theme
//
// Validates: Requirements 6.1, 6.2, 6.4, 8.8 — for all active themes and for all defined
// foreground/background token pairings used together (normal text, large text, status
// graphical elements, and focus-indicator vs. adjacent), the rendered contrast ratio meets
// the applicable WCAG AA threshold:
//   - 4.5:1 for normal-size text                                        (Req 6.1)
//   - 3:1   for large-size text and status graphical elements           (Req 6.2)
//   - 3:1   for focus indicators against their adjacent colour          (Req 6.4)
//   - Both themes maintain these ratios                                 (Req 8.8)
//
// Strategy (per design.md Testing Strategy):
//   * Use fast-check with a minimum of 100 iterations.
//   * Generators draw from the actual enumerated theme set and the actual TOKEN_PAIRINGS
//     map declared in `a11y/contrast.ts` (not random colours) — Property 6 is about the
//     chosen palette, not arbitrary colour cross-products.
//   * Contrast is computed via `contrastForPairing(...)`, which composites translucent
//     surfaces and any translucent foreground onto an opaque base before applying the
//     WCAG 2.1 relative-luminance formula. This matches what a user actually sees.

import * as fc from "fast-check";
import {
  THEME_TOKEN_VALUES,
  TOKEN_PAIRINGS,
  contrastForPairing,
} from "../a11y";
import type { ThemeName, TokenPairing } from "../a11y";

// ---------------------------------------------------------------------------
// Generators — enumerate the *real* theme/pairing inputs, not arbitrary values
// ---------------------------------------------------------------------------

const THEMES: readonly ThemeName[] = ["light", "dark"] as const;
const arbTheme = fc.constantFrom<ThemeName>(...THEMES);
const arbPairing = fc.constantFrom<TokenPairing>(...TOKEN_PAIRINGS);

// ---------------------------------------------------------------------------
// Sanity-fail-fast: ensure the inputs are non-empty so an empty enumeration
// doesn't silently make the property test pass with zero work.
// ---------------------------------------------------------------------------

if (TOKEN_PAIRINGS.length === 0) {
  throw new Error(
    "contrast.property.test: TOKEN_PAIRINGS is empty — Property 6 cannot be asserted."
  );
}
for (const theme of THEMES) {
  const tokenCount = Object.keys(THEME_TOKEN_VALUES[theme]).length;
  if (tokenCount === 0) {
    throw new Error(
      `contrast.property.test: THEME_TOKEN_VALUES["${theme}"] is empty — check tokens.css ` +
        "parsing in src/a11y/contrast.ts."
    );
  }
}

// ---------------------------------------------------------------------------
// Property 6
// ---------------------------------------------------------------------------

describe("Property 6: Palette contrast meets WCAG AA in every theme", () => {
  it(
    "every (theme, pairing) yields contrast >= the pairing's WCAG AA threshold",
    () => {
      fc.assert(
        fc.property(arbTheme, arbPairing, (theme, pairing) => {
          const ratio = contrastForPairing(pairing, theme);

          // The ratio must meet the WCAG AA threshold for this pairing's category.
          // Allow a 0.005 tolerance for floating-point composite arithmetic so
          // values like 4.499999... that round to 4.50 in audits are not flagged.
          const tolerance = 0.005;
          const meetsThreshold = ratio + tolerance >= pairing.threshold;

          if (!meetsThreshold) {
            // Embed full diagnostic context so a failure shrinks to a useful message.
            throw new Error(
              `Pairing "${pairing.id}" (${pairing.category}) fails WCAG AA in the "${theme}" theme: ` +
                `contrast ${ratio.toFixed(3)}:1 < required ${pairing.threshold}:1. ` +
                `foreground=${pairing.foreground}, ` +
                `backgroundLayers=[${pairing.backgroundLayers.join(", ")}], ` +
                `description: ${pairing.description}`
            );
          }

          // Sanity bound — every WCAG contrast ratio is in [1, 21].
          expect(ratio).toBeGreaterThanOrEqual(1);
          expect(ratio).toBeLessThanOrEqual(21);
        }),
        { numRuns: 100, verbose: false }
      );
    }
  );

  // -------------------------------------------------------------------------
  // Exhaustive cross-product check (not PBT) — guarantees that every single
  // (theme × pairing) combination is asserted at least once even if fast-check
  // happens not to sample some pair during its 100 runs. The property test
  // above remains the canonical statement; this complements it so the property
  // cannot pass while a specific corner pairing has never actually been tested.
  // -------------------------------------------------------------------------
  it("every theme × pairing combination is exhaustively verified", () => {
    const failures: string[] = [];
    for (const theme of THEMES) {
      for (const pairing of TOKEN_PAIRINGS) {
        const ratio = contrastForPairing(pairing, theme);
        if (ratio + 0.005 < pairing.threshold) {
          failures.push(
            `[${theme}] ${pairing.id} (${pairing.category}): ` +
              `${ratio.toFixed(3)}:1 < ${pairing.threshold}:1`
          );
        }
      }
    }
    expect(
      failures,
      `WCAG AA contrast failures:\n  ${failures.join("\n  ")}`
    ).toEqual([]);
  });
});
