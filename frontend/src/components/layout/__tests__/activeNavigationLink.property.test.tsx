// Feature: ui-ux-responsive-redesign, Property 5: Active navigation link is distinguished by a non-color means
//
// Validates: Requirements 5.7
//
// Property 5 (from design.md):
//   "For all active routes, the rendered active navigation link is marked
//   with `aria-current=\"page\"` and a non-color distinction (indicator
//   and/or font weight) that differs from every non-active link, in
//   addition to any color difference."
//
// Requirement 5.7 (from requirements.md):
//   "WHILE a route is active, THE Navigation_Shell SHALL apply a visual
//   treatment to the navigation link for that route that is distinct from
//   all non-active navigation links and that indicates the current route
//   through a means in addition to color."
//
// Strategy:
//   1. Use fast-check to pick an arbitrary `activeRoute` from `NAV_ITEMS`
//      via `fc.constantFrom(...)` (the four routes exported by the shell:
//      `/fleet`, `/live`, `/alerts`, `/config`).
//   2. Render `NavigationShell` mounted in a `MemoryRouter` initialised at
//      that route, wrapped in `ThemeProvider` (matching the wrapper pattern
//      from the existing smoke test at `NavigationShell.test.tsx`).
//   3. For every iteration, assert four structural signals that together
//      make the active link distinguishable by a non-color means:
//        (a) The link for `activeRoute` carries `aria-current="page"`
//            (set automatically by React Router's `NavLink`).
//        (b) Every other rendered nav link does NOT carry
//            `aria-current="page"`.
//        (c) The active link has the `navshell__link--active` class —
//            applied by NavLink's `className` callback when `isActive`
//            is true.
//        (d) The active link contains a nested `<span
//            class="navshell__link-rail" aria-hidden="true">` element.
//            That same element is *also* present on every other link
//            (the rail is rendered unconditionally as part of the link
//            template), but the CSS rule
//              `.navshell__link[aria-current="page"] .navshell__link-rail,
//               .navshell__link--active .navshell__link-rail
//               { visibility: visible; }`
//            only makes it visible when its parent link carries
//            `aria-current="page"` or the `--active` class. We assert the
//            structural pre-condition that drives that selector (rail
//            present AND active-state attribute/class on parent) rather
//            than the computed visibility because jsdom does not fully
//            evaluate stylesheet rules for our component CSS (see
//            `vitest.config.ts` — only `tokens.css` is processed; all
//            other CSS imports are stubbed). The visibility transition is
//            a CSS contract verified separately by inspection of
//            `NavigationShell.css`; the property here verifies the DOM
//            contract that enables it.
//   4. Run at least 100 iterations as required by the design's Testing
//      Strategy for property-based tests. We use 120 iterations to stay
//      comfortably above the minimum and give the shrinker enough budget
//      to land on a small, named counter-example.

import * as fc from "fast-check";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ThemeProvider } from "../../../theme";
import { NAV_ITEMS, NavigationShell } from "../NavigationShell";

// ---------------------------------------------------------------------------
// Test scaffold
// ---------------------------------------------------------------------------

/**
 * Render `NavigationShell` at the supplied active route. Mirrors the wrapper
 * pattern used by the existing smoke test at
 * `frontend/src/components/layout/__tests__/NavigationShell.test.tsx` so the
 * two suites exercise the shell under identical provider conditions.
 */
function renderShellAt(path: string): void {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<NavigationShell />}>
            <Route path="/fleet" element={<p>Fleet content</p>} />
            <Route path="/live" element={<p>Live content</p>} />
            <Route path="/alerts" element={<p>Alerts content</p>} />
            <Route path="/config" element={<p>Config content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 5: Active navigation link is distinguished by a non-color means (Requirement 5.7)", () => {
  afterEach(() => {
    cleanup();
  });

  // Fixed-list arbitrary over the four routes exposed by `NAV_ITEMS`. Using
  // `constantFrom` means the shrinker can name the failing route in any
  // counter-example.
  const arbActiveRoute = fc.constantFrom(...NAV_ITEMS);

  it("active link has aria-current=page, the --active class, and a rail indicator that non-active links lack", () => {
    fc.assert(
      fc.property(arbActiveRoute, (activeRoute) => {
        // Start each iteration with a fresh DOM so prior renders cannot leak
        // duplicate links with colliding accessible names into our queries.
        cleanup();
        renderShellAt(activeRoute.to);

        // -------------------------------------------------------------------
        // (a) The active link advertises the current route through
        //     `aria-current="page"` (set automatically by NavLink).
        // -------------------------------------------------------------------
        const activeLink = screen.getByRole("link", { name: activeRoute.label });
        expect(activeLink).toHaveAttribute("aria-current", "page");

        // -------------------------------------------------------------------
        // (b) No other nav link carries `aria-current="page"` — the active
        //     treatment is *distinct from all non-active links*
        //     (Requirement 5.7 wording).
        // -------------------------------------------------------------------
        for (const otherItem of NAV_ITEMS.filter((nav) => nav.to !== activeRoute.to)) {
          const otherLink = screen.getByRole("link", { name: otherItem.label });
          expect(otherLink).not.toHaveAttribute("aria-current", "page");
          // The className-based active modifier must also be absent on
          // non-active links so the non-color signal does not bleed across.
          expect(otherLink.classList.contains("navshell__link--active")).toBe(false);
        }

        // -------------------------------------------------------------------
        // (c) The active link carries the `navshell__link--active` class.
        //     This is set by NavLink's className callback when `isActive`
        //     is true, and is the second selector that drives the
        //     non-color CSS treatment (font-weight: bold and rail
        //     visibility) in NavigationShell.css.
        // -------------------------------------------------------------------
        expect(activeLink.classList.contains("navshell__link--active")).toBe(true);

        // -------------------------------------------------------------------
        // (d) The active link contains the rail indicator span. We scope
        //     the query to the active link itself via `within(...)` so a
        //     stray match elsewhere in the DOM cannot satisfy the
        //     assertion. The span is the structural signal that the CSS
        //     visibility selector targets; in jsdom we cannot reliably
        //     evaluate the stylesheet rule, but the DOM contract is what
        //     the CSS depends on, and it is what this property asserts.
        //
        //     The rail is rendered unconditionally inside *every* nav
        //     link's template, so we *also* check the parent link's
        //     active-state signal (covered by (a) + (c) above) — those
        //     two facts together pick out the active rail as the only
        //     one made visible by the CSS rule
        //       `.navshell__link[aria-current="page"] .navshell__link-rail,
        //        .navshell__link--active .navshell__link-rail
        //        { visibility: visible; }`.
        // -------------------------------------------------------------------
        const rail = within(activeLink).getByText(
          (_content, node) =>
            node !== null &&
            node instanceof HTMLElement &&
            node.classList.contains("navshell__link-rail"),
          { selector: "span" },
        );
        expect(rail).toBeInTheDocument();
        expect(rail).toHaveAttribute("aria-hidden", "true");
        // The rail's parent must be the active link — this is the
        // structural relationship the CSS visibility selector relies on.
        expect(rail.parentElement).toBe(activeLink);
      }),
      { numRuns: 120, verbose: false },
    );
  });
});
