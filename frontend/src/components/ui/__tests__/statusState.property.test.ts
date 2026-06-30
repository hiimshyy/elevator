// Feature: ui-ux-responsive-redesign, Property 2: Status indicators are distinct by a non-color attribute

/**
 * Property-based tests for status-state visual distinctness.
 *
 * Validates: Requirements 3.6, 3.7, 6.3
 *
 * Property 2a — Pairwise distinctness:
 *   For all ordered pairs of distinct status states (A, B), their visual
 *   treatments differ in at least one non-color attribute (icon, shape, or label).
 *
 * Property 2b — Non-color signal present:
 *   For all status states, the visual treatment includes at least one
 *   non-color signal — specifically a non-empty icon AND a non-empty label.
 */

import * as fc from "fast-check";
import {
  type StatusState,
  STATUS_VISUALS,
  getStatusVisual,
} from "../statusState";

const ALL_STATES: StatusState[] = ["healthy", "warning", "critical", "unknown"];

describe("Property 2: Status indicators are distinct by a non-color attribute", () => {
  /**
   * Property 2a — Pairwise distinctness
   * Validates: Requirements 3.7, 3.6
   *
   * For every ordered pair (stateA, stateB) where stateA !== stateB,
   * their visual treatments must differ in at least one of: icon, shape, or label.
   */
  it("2a: any two distinct status states differ in at least one non-color attribute", () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.constantFrom(...ALL_STATES), {
          minLength: 2,
          maxLength: 2,
        }),
        ([stateA, stateB]) => {
          const visualA = getStatusVisual(stateA);
          const visualB = getStatusVisual(stateB);

          const differsByIcon = visualA.icon !== visualB.icon;
          const differsByShape = visualA.shape !== visualB.shape;
          const differsByLabel = visualA.label !== visualB.label;

          return differsByIcon || differsByShape || differsByLabel;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 2b — Non-color signal present
   * Validates: Requirements 6.3, 3.6
   *
   * For every status state, the visual treatment must carry a non-empty icon
   * AND a non-empty text label — providing non-color signals alongside color.
   */
  it("2b: every status state visual includes a non-empty icon and a non-empty label", () => {
    fc.assert(
      fc.property(fc.constantFrom(...ALL_STATES), (state) => {
        const visual = getStatusVisual(state);

        const hasIcon = typeof visual.icon === "string" && visual.icon.trim().length > 0;
        const hasLabel = typeof visual.label === "string" && visual.label.trim().length > 0;

        return hasIcon && hasLabel;
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Exhaustive sanity check — all four states are covered in STATUS_VISUALS
   * and each has a distinct icon, label, and shape across the full set.
   */
  it("all four states have mutually distinct icons, labels, and shapes", () => {
    const visuals = ALL_STATES.map((s) => STATUS_VISUALS[s]);

    const icons = visuals.map((v) => v.icon);
    const labels = visuals.map((v) => v.label);
    const shapes = visuals.map((v) => v.shape);

    expect(new Set(icons).size).toBe(ALL_STATES.length);
    expect(new Set(labels).size).toBe(ALL_STATES.length);
    expect(new Set(shapes).size).toBe(ALL_STATES.length);
  });
});
