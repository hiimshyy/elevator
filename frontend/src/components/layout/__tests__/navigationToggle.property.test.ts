// Feature: ui-ux-responsive-redesign, Property 4: For all navigation states, applying the menu toggle once flips the expanded/collapsed state and applying it twice returns to the original state; and for all navigation states while in collapsible mode, performing a link-selection action results in the navigation being collapsed.
//
// Validates: Requirements 5.3, 5.4, 5.5
//
// Property 4 (from design.md):
//   "For all navigation states, applying the menu toggle once flips the
//    expanded/collapsed state and applying it twice returns to the
//    original state; and for all navigation states while in collapsible
//    mode, performing a link-selection action results in the navigation
//    being collapsed."
//
// Requirements (from requirements.md):
//   5.3 — WHEN a user activates the menu control while the primary
//         navigation is collapsed, THE Navigation_Shell SHALL display the
//         primary navigation links.
//   5.4 — WHEN a user activates the menu control while the primary
//         navigation is expanded, THE Navigation_Shell SHALL collapse the
//         primary navigation.
//   5.5 — WHEN a user selects a navigation link while the primary
//         navigation is collapsed-capable, THE Navigation_Shell SHALL
//         navigate to the selected route and collapse the primary
//         navigation.
//
// Strategy:
//   The pure reducer `navReducer` is the single source of truth for the
//   toggle/select-link state transitions consumed by NavigationShell.
//   Rendering the full shell to exercise these transitions adds router
//   plumbing without exercising more logic — design.md explicitly exports
//   the reducer so that it can be tested in isolation. We therefore drive
//   `navReducer` directly and assert three claims that together capture
//   Property 4:
//     (1) `toggle` once flips `isExpanded` from any starting state
//         (Requirements 5.3, 5.4).
//     (2) `toggle` is an involution: applying it twice from any state
//         (including any state reachable after an arbitrary sequence of
//         prior actions) returns to that state.
//     (3) `selectLink` from any state yields `isExpanded === false`
//         (Requirement 5.5). The "collapsible mode" qualifier in the
//         property statement refers to where the action is dispatched
//         (the component only dispatches `selectLink` in collapsible
//         mode), not to a branch in the reducer itself — the reducer's
//         post-condition is unconditional, which is what we test here.
//
//   To strengthen the involution claim across longer histories we also
//   drive a randomised sequence of actions through the reducer and
//   re-verify the involution from the final reached state.
//
//   fast-check is the established property-based testing library for the
//   TypeScript/JS ecosystem and is the framework specified in design.md
//   (Testing Strategy → Tooling). We run 200 iterations, comfortably
//   above the design's 100-iteration minimum, to give the shrinker
//   enough budget to land on a minimal counter-example if one exists.

import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  initialNavState,
  navReducer,
  type NavAction,
  type NavState,
} from "../NavigationShell";

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

/**
 * Arbitrary navigation state. The state space is small (one boolean), so an
 * enumeration covers it exhaustively; using `fc.record` lets the shrinker
 * report a clean `{ isExpanded: ... }` value in counter-examples.
 */
const arbNavState: fc.Arbitrary<NavState> = fc.record({
  isExpanded: fc.boolean(),
});

/**
 * Arbitrary reducer action drawn from the discriminated union exported by
 * NavigationShell. Both action types are equally likely so each branch of
 * the reducer is exercised across the run.
 */
const arbNavAction: fc.Arbitrary<NavAction> = fc.oneof(
  fc.constant<NavAction>({ type: "toggle" }),
  fc.constant<NavAction>({ type: "selectLink" }),
);

/**
 * A sequence of 0–20 reducer actions. Used to drive the reducer through an
 * arbitrary history before re-verifying the involution from the resulting
 * state, demonstrating that the property holds for any reachable state and
 * not only the two enumerated initial states.
 */
const arbActionSequence: fc.Arbitrary<readonly NavAction[]> = fc.array(arbNavAction, {
  minLength: 0,
  maxLength: 20,
});

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 4: Navigation toggle is an involution and link selection collapses (Requirements 5.3, 5.4, 5.5)", () => {
  it("toggle once flips isExpanded, toggle twice is identity, and selectLink collapses — across arbitrary histories", () => {
    fc.assert(
      fc.property(arbNavState, arbActionSequence, (start, history) => {
        // -------------------------------------------------------------------
        // (1) `toggle` once flips `isExpanded`. Requirements 5.3 (collapsed
        //     → expanded) and 5.4 (expanded → collapsed) together say that
        //     a single activation of the menu control always swaps the
        //     drawer state.
        // -------------------------------------------------------------------
        const afterOne = navReducer(start, { type: "toggle" });
        expect(afterOne.isExpanded).toBe(!start.isExpanded);

        // -------------------------------------------------------------------
        // (2) `toggle` is an involution from the enumerated starting state.
        //     Applying it twice must yield a state value-equal to the start.
        // -------------------------------------------------------------------
        const afterTwo = navReducer(afterOne, { type: "toggle" });
        expect(afterTwo).toEqual(start);

        // -------------------------------------------------------------------
        // (3) `selectLink` collapses the nav from any starting state
        //     (Requirement 5.5). The reducer's post-condition is
        //     unconditional — the component restricts dispatching
        //     `selectLink` to collapsible mode, but the reducer itself
        //     must always produce `isExpanded === false`.
        // -------------------------------------------------------------------
        const afterSelect = navReducer(start, { type: "selectLink" });
        expect(afterSelect.isExpanded).toBe(false);

        // -------------------------------------------------------------------
        // Long-history reinforcement of the involution claim: drive the
        // reducer through an arbitrary sequence of toggle/selectLink
        // actions, then re-verify that one more `toggle` flips the
        // resulting state and a second `toggle` returns to it. This
        // guards against any future change that might make the reducer
        // history-dependent (e.g. accumulating extra fields on NavState)
        // while still passing the two enumerated cases above.
        // -------------------------------------------------------------------
        const reached: NavState = history.reduce<NavState>(
          (state, action) => navReducer(state, action),
          start,
        );
        const reachedAfterOne = navReducer(reached, { type: "toggle" });
        const reachedAfterTwo = navReducer(reachedAfterOne, { type: "toggle" });
        expect(reachedAfterOne.isExpanded).toBe(!reached.isExpanded);
        expect(reachedAfterTwo).toEqual(reached);

        // And `selectLink` from any reachable state still collapses.
        const reachedAfterSelect = navReducer(reached, { type: "selectLink" });
        expect(reachedAfterSelect.isExpanded).toBe(false);
      }),
      { numRuns: 200, verbose: false },
    );
  });

  it("sanity: the exported initial state is collapsed, so the property covers the production starting point", () => {
    // Documents the entry point the reducer is wired to in NavigationShell.
    // The property above already covers `{ isExpanded: false }` as one of
    // the two values produced by `arbNavState`, but stating it explicitly
    // here keeps the link to the component's actual initial state visible
    // in the test file.
    expect(initialNavState).toEqual({ isExpanded: false });
  });
});
