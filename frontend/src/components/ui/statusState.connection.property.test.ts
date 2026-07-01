// Feature: ui-ux-responsive-redesign, Property 13: Connection states map to three mutually distinct treatments

/**
 * Property-based tests for connection-state visual treatments.
 *
 * Validates: Requirements 7.7
 *
 * Property 13 — Connection states map to three mutually distinct treatments:
 *   For all three connection states (connected, connecting, disconnected),
 *   the connection Status_Indicator produces three pairwise-distinct visual
 *   treatments. Concretely, resolving each ConnectionState via
 *   `mapConnectionStateToState` and then `getStatusVisual` yields StatusVisual
 *   objects that differ pairwise in at least one non-color attribute
 *   (icon, label, or shape), and — stronger — the three visuals form a set
 *   of size 3 across every attribute (color, icon, label, shape).
 */

import * as fc from "fast-check";
import {
  type ConnectionState,
  getStatusVisual,
  mapConnectionStateToState,
} from "./statusState";

const ALL_CONNECTION_STATES: ConnectionState[] = [
  "connected",
  "connecting",
  "disconnected",
];

/** Resolve the StatusVisual for a ConnectionState in one step. */
function visualFor(state: ConnectionState) {
  return getStatusVisual(mapConnectionStateToState(state));
}

describe("Property 13: Connection states map to three mutually distinct treatments", () => {
  /**
   * Property 13a — Pairwise non-color distinctness
   * Validates: Requirements 7.7
   *
   * For every ordered pair (stateA, stateB) of distinct ConnectionStates,
   * the resolved StatusVisual must differ in at least one non-color attribute
   * (icon, label, or shape). This ensures the connection indicator is
   * distinguishable without relying on color alone.
   */
  it("13a: any two distinct connection states differ in at least one non-color attribute", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...ALL_CONNECTION_STATES),
        fc.constantFrom(...ALL_CONNECTION_STATES),
        (stateA, stateB) => {
          fc.pre(stateA !== stateB);

          const visualA = visualFor(stateA);
          const visualB = visualFor(stateB);

          const differsByIcon = visualA.icon !== visualB.icon;
          const differsByLabel = visualA.label !== visualB.label;
          const differsByShape = visualA.shape !== visualB.shape;

          return differsByIcon || differsByLabel || differsByShape;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 13b — Pairwise full-attribute distinctness (stronger)
   * Validates: Requirements 7.7
   *
   * For every ordered pair (stateA, stateB) of distinct ConnectionStates,
   * the resolved StatusVisual must differ in every attribute: color, icon,
   * label, and shape. This is a stronger guarantee than 13a: it ensures the
   * three connection states are fully separable on every channel.
   */
  it("13b: any two distinct connection states differ in color, icon, label, and shape", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...ALL_CONNECTION_STATES),
        fc.constantFrom(...ALL_CONNECTION_STATES),
        (stateA, stateB) => {
          fc.pre(stateA !== stateB);

          const visualA = visualFor(stateA);
          const visualB = visualFor(stateB);

          return (
            visualA.color !== visualB.color &&
            visualA.icon !== visualB.icon &&
            visualA.label !== visualB.label &&
            visualA.shape !== visualB.shape
          );
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Exhaustive sanity check — all three connection states produce three
   * mutually distinct visual treatments across every attribute. Because the
   * domain has only three elements, this deterministic check complements the
   * randomized property runs above.
   */
  it("all three connection states produce three mutually distinct visual treatments", () => {
    const visuals = ALL_CONNECTION_STATES.map(visualFor);

    const colors = visuals.map((v) => v.color);
    const icons = visuals.map((v) => v.icon);
    const labels = visuals.map((v) => v.label);
    const shapes = visuals.map((v) => v.shape);

    expect(new Set(colors).size).toBe(ALL_CONNECTION_STATES.length);
    expect(new Set(icons).size).toBe(ALL_CONNECTION_STATES.length);
    expect(new Set(labels).size).toBe(ALL_CONNECTION_STATES.length);
    expect(new Set(shapes).size).toBe(ALL_CONNECTION_STATES.length);

    // Also verify the combined visual signature yields three distinct rows.
    const signatures = visuals.map(
      (v) => `${v.color}|${v.icon}|${v.label}|${v.shape}`
    );
    expect(new Set(signatures).size).toBe(ALL_CONNECTION_STATES.length);
  });
});
