// Feature: ui-ux-responsive-redesign, Property 11: Error state preserves prior data and describes the failure
//
// Validates: Requirements 7.4
//
// Property 11 (from design.md):
//   For all previously loaded data, view names, and failure reasons,
//   transitioning a view's Data_State to error preserves the previously
//   loaded data unchanged, exposes a retry control, and produces a
//   message containing both the affected view name and the failure
//   reason.
//
// Requirement 7.4 (from requirements.md):
//   "IF a data request fails, THEN THE Operations_Console SHALL display
//   an error message that identifies the affected view, states the
//   failure reason, and presents a retry control, while preserving any
//   previously loaded data for that view."
//
// Scope:
//   This is a pure-function property test against the `failError`
//   transition (and equivalently the `viewStateReducer` "failError"
//   action) exposed by `frontend/src/lib/viewState.ts`. The
//   retry-control claim from Property 11 is a structural claim about
//   the public API surface (`retry`/`useViewState.retry`) verified by
//   the timing/integration tests in task 14.4 and is intentionally not
//   re-asserted here.

import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  failError,
  viewStateReducer,
  type DataState,
  type ViewDataState,
} from "./viewState";

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

// Prior `data` payloads. Includes the `null` branch because
// "loading-before-first-success" is a valid prior state in which an error
// may occur, and we still need to verify the reference is preserved. We
// use `fc.anything()` to cover arbitrary structured payloads (objects,
// arrays, nested mixes, primitives) so the reference-equality claim is
// exercised against the full range of value shapes the reducer may carry.
const arbPrevData: fc.Arbitrary<unknown> = fc.oneof(
  fc.constant(null),
  fc.anything(),
);

// Prior `state` label. Any of the four data-states may precede a
// failError transition (e.g. populated->error on refresh, loading->error
// on initial fetch).
const arbPrevState: fc.Arbitrary<DataState> = fc.constantFrom<DataState>(
  "loading",
  "empty",
  "error",
  "populated",
);

// `lastUpdatedAt` is either an ISO timestamp string or null. We don't
// require a real ISO format here — the reducer treats it opaquely and
// the property is just that the field is preserved unchanged.
const arbLastUpdatedAt: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant<string | null>(null),
  fc.string(),
);

const arbPrevError: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant<string | null>(null),
  fc.string(),
);

const arbPrev: fc.Arbitrary<ViewDataState<unknown>> = fc
  .record({
    state: arbPrevState,
    data: arbPrevData,
    error: arbPrevError,
    lastUpdatedAt: arbLastUpdatedAt,
  })
  .map((r) => r as ViewDataState<unknown>);

// View labels are human-readable view names. Constrained to non-empty so
// the "contains the affected view name" claim is meaningful (an empty
// substring is contained by every string and would make the assertion
// vacuous).
const arbViewLabel: fc.Arbitrary<string> = fc
  .oneof(
    fc.unicodeString({ minLength: 1, maxLength: 48 }),
    fc.string({ minLength: 1, maxLength: 48 }),
  )
  .filter((s) => s.length > 0);

// Failure reasons. Includes empty + whitespace-only strings to exercise
// the "no reason" branch of `buildViewStateErrorMessage`, which omits
// the trailing ": <reason>" clause when `reason.trim()` is empty.
const arbReason: fc.Arbitrary<string> = fc.oneof(
  fc.constant(""),
  fc.constant("   "),
  fc.constant("\t\n"),
  fc.unicodeString({ maxLength: 64 }),
  fc.string({ maxLength: 64 }),
);

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 11: Error state preserves prior data and describes the failure (Requirement 7.4)", () => {
  it("failError preserves prior data and produces a message naming the view and reason", () => {
    fc.assert(
      fc.property(arbPrev, arbViewLabel, arbReason, (prev, viewLabel, reason) => {
        const result = failError(prev, viewLabel, reason);

        // 1. Transition lands in the error state.
        expect(result.state).toBe("error");

        // 2. Previously loaded data is preserved by reference (not deep-
        //    copied). This is what guarantees Requirement 7.4's
        //    "preserving any previously loaded data" without imposing a
        //    cloning cost on the reducer.
        expect(result.data).toBe(prev.data);

        // 3. The error message is a non-empty string that names the
        //    affected view, and — when a non-whitespace reason is
        //    provided — also includes the failure reason.
        expect(typeof result.error).toBe("string");
        expect(result.error).not.toBeNull();
        const message = result.error as string;
        expect(message.length).toBeGreaterThan(0);
        expect(message).toContain(viewLabel);

        const trimmedReason = reason.trim();
        if (trimmedReason.length > 0) {
          expect(message).toContain(trimmedReason);
        }

        // 4. `lastUpdatedAt` is preserved so the previously displayed
        //    data is still presented "as of" its original timestamp.
        expect(result.lastUpdatedAt).toBe(prev.lastUpdatedAt);
      }),
      { numRuns: 100 },
    );
  });

  it("the reducer's failError action is equivalent to the failError transition", () => {
    fc.assert(
      fc.property(arbPrev, arbViewLabel, arbReason, (prev, viewLabel, reason) => {
        const viaTransition = failError(prev, viewLabel, reason);
        const viaReducer = viewStateReducer(prev, {
          type: "failError",
          viewLabel,
          reason,
        });

        // Reducer path must agree with the pure transition path on every
        // field — same state, same preserved data reference, same
        // composed message, same preserved timestamp.
        expect(viaReducer.state).toBe(viaTransition.state);
        expect(viaReducer.data).toBe(viaTransition.data);
        expect(viaReducer.error).toBe(viaTransition.error);
        expect(viaReducer.lastUpdatedAt).toBe(viaTransition.lastUpdatedAt);
      }),
      { numRuns: 100 },
    );
  });
});
