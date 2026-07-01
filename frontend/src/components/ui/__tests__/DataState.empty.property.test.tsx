// Feature: ui-ux-responsive-redesign, Property 10: Empty state names the missing data
//
// Validates: Requirements 7.3
//
// Property 10 (from design.md):
//   For all view labels, the rendered empty Data_State message contains the
//   name of the missing data for that view.
//
// Requirement 7.3 (from requirements.md):
//   WHILE a Data_State is empty, THE Operations_Console SHALL display an
//   empty-state message that names the missing data for the affected view.
//
// Test strategy
// -------------
// `DataState` (frontend/src/components/ui/DataState.tsx) exposes a
// `missingDataLabel` prop carrying the plural noun for the data that is
// missing in the empty presentation. The current implementation composes
// the message as `No ${missingDataLabel ?? viewLabel} to display`, so the
// "name of the missing data for that view" is whichever of those two
// strings is in effect.
//
// To exercise Property 10 we universally quantify over both forms of the
// missing-data name:
//
//   1. When `missingDataLabel` is supplied, the rendered text must contain
//      that label verbatim.
//   2. When `missingDataLabel` is omitted, the rendered text must contain
//      the `viewLabel` (the documented fallback that keeps the empty state
//      naming *something*).
//
// Each iteration renders the component, locates the empty-state container
// by its stable `data-state="empty"` attribute, and asserts substring
// containment on its `textContent`. Substring containment (vs a regex)
// avoids any regex-escaping pitfalls for arbitrary unicode labels.

import { cleanup, render } from "@testing-library/react";
import * as fc from "fast-check";
import { afterEach, describe, expect, it } from "vitest";

import { LiveRegionProvider } from "../../../a11y";
import { DataState } from "../DataState";

afterEach(() => {
  // Each fast-check iteration mounts a fresh DataState; without an explicit
  // cleanup the previous render's DOM would leak into the next iteration's
  // textContent queries.
  cleanup();
});

/**
 * Non-blank unicode strings up to 64 chars. The trim()-based filter rejects
 * pure-whitespace inputs so the substring assertion remains meaningful
 * (whitespace-only labels would trivially appear inside any rendered text).
 * `fc.unicodeString` excludes lone surrogates that React would otherwise
 * refuse to render.
 */
const arbNonBlankString = fc
  .unicodeString({ minLength: 1, maxLength: 64 })
  .filter((s) => s.trim().length > 0);

describe("Property 10: Empty state names the missing data (Requirement 7.3)", () => {
  it("contains the supplied missingDataLabel in the rendered empty-state text", () => {
    fc.assert(
      fc.property(
        arbNonBlankString,
        arbNonBlankString,
        (viewLabel, missingDataLabel) => {
          cleanup();
          const { container } = render(
            <LiveRegionProvider>
              <DataState
                state="empty"
                viewLabel={viewLabel}
                missingDataLabel={missingDataLabel}
              />
            </LiveRegionProvider>
          );

          const emptyNode = container.querySelector('[data-state="empty"]');
          expect(emptyNode).not.toBeNull();
          const renderedText = emptyNode!.textContent ?? "";
          expect(renderedText.includes(missingDataLabel)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("falls back to naming the view when missingDataLabel is omitted", () => {
    fc.assert(
      fc.property(arbNonBlankString, (viewLabel) => {
        cleanup();
        const { container } = render(
          <LiveRegionProvider>
            <DataState state="empty" viewLabel={viewLabel} />
          </LiveRegionProvider>
        );

        const emptyNode = container.querySelector('[data-state="empty"]');
        expect(emptyNode).not.toBeNull();
        const renderedText = emptyNode!.textContent ?? "";
        expect(renderedText.includes(viewLabel)).toBe(true);
      }),
      { numRuns: 100 }
    );
  });
});
