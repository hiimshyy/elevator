// Feature: ui-ux-responsive-redesign, Property 9: Chart text alternative includes latest value, unit, and timestamp
//
// Validates: Requirements 6.9
//
// Property 9 (from design.md):
//   For all non-empty telemetry series with a unit and timestamps, the
//   chart's accessible text alternative contains the latest value, the
//   metric unit, and the timestamp of the latest value.
//
// Requirement 6.9 (from requirements.md):
//   "WHERE a chart renders telemetry data, THE Live_Telemetry_View SHALL
//   provide an accessible text alternative that includes the latest
//   value, the metric unit, and the timestamp of the latest value."
//
// Scope:
//   This is a pure-function property test against the exported helper
//   `buildChartAccessibleLabel` in
//   `frontend/src/components/charts/MetricSparkline.tsx`. That helper is
//   the single source of truth for both the SVG's `aria-label` and the
//   visually-hidden text alternative rendered inside the chart card, so
//   verifying its output is sufficient to verify the accessible text
//   alternative surfaced by <MetricSparkline />.
//
//   The synthetic-trace label (Requirement 7.6, Property 12) and
//   connection-state treatments (Requirement 7.7, Property 13) are
//   covered by their own property tests and are intentionally not
//   asserted here.

import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import { buildChartAccessibleLabel } from "./MetricSparkline";

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

// Human-readable metric label. Requirement 6.9 speaks of "a chart" —
// any non-empty display name is valid, including strings that contain
// unicode / whitespace. We filter for a non-whitespace character so the
// label is a meaningful, distinguishable value (the property is about
// containment; an all-whitespace label would still trivially satisfy
// containment but would produce a vacuous assertion).
const arbLabel: fc.Arbitrary<string> = fc
  .unicodeString({ minLength: 1, maxLength: 48 })
  .filter((s) => s.trim().length > 0);

// Value series. Bounded to [1, 60] points to mirror the ~60-sample
// rolling window used by the Live Monitor route. All values must be
// finite (no NaN, no Infinity) — the accessible label branches on
// `Number.isFinite(latestValue)` and would degrade to a "No data
// available" string for non-finite inputs, so restricting the input
// space here mirrors the property's precondition ("non-empty telemetry
// series with a unit and timestamps").
const arbPoints: fc.Arbitrary<number[]> = fc.array(
  fc.float({ noNaN: true, noDefaultInfinity: true }),
  { minLength: 1, maxLength: 60 },
);

// Metric unit (e.g. "mg", "mm/s", "kg", "C"). Any non-empty unicode
// string is a valid unit for the purposes of the accessible-label
// contract; we filter whitespace-only strings for the same reason as
// the label generator above.
const arbUnit: fc.Arbitrary<string> = fc
  .unicodeString({ minLength: 1, maxLength: 16 })
  .filter((s) => s.trim().length > 0);

// Valid ISO-8601 timestamp string. `fc.date()` produces a JS Date whose
// `.toISOString()` output is always a non-empty ISO string like
// "2024-04-15T12:34:56.789Z". This matches what the WebSocket telemetry
// pipeline passes in via `latestTimestamp`.
const arbTimestamp: fc.Arbitrary<string> = fc
  .date({ noInvalidDate: true })
  .map((d) => d.toISOString());

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 9: Chart text alternative includes latest value, unit, and timestamp (Requirement 6.9)", () => {
  it("buildChartAccessibleLabel contains String(latestValue), the unit, and the raw ISO timestamp for any non-empty series", () => {
    fc.assert(
      fc.property(arbLabel, arbPoints, arbUnit, arbTimestamp, (label, points, unit, timestamp) => {
        // Precondition of Property 9: the telemetry series is non-empty.
        // `arbPoints` already enforces `minLength: 1`, so `latestValue`
        // is always defined and finite (fast-check's `noNaN` +
        // `noDefaultInfinity` constraints guarantee finiteness).
        const latestValue = points[points.length - 1];
        expect(Number.isFinite(latestValue)).toBe(true);

        const label_ = buildChartAccessibleLabel(label, latestValue, unit, timestamp);

        // The accessible text alternative must be a non-empty string —
        // an empty label would fail the "provides an accessible text
        // alternative" clause of Requirement 6.9 outright.
        expect(typeof label_).toBe("string");
        expect(label_.length).toBeGreaterThan(0);

        // Property 9 clause 1 — includes the latest value.
        // We compare against `String(latestValue)` (rather than
        // `latestValue.toFixed(n)` or `Intl.NumberFormat(...)`) because
        // the implementation itself emits the raw stringified number in
        // the accessible label, and that is the shape assistive tech
        // consumes.
        expect(label_).toContain(String(latestValue));

        // Property 9 clause 2 — includes the metric unit.
        expect(label_).toContain(unit);

        // Property 9 clause 3 — includes the timestamp of the latest
        // value. We assert containment of the raw ISO string rather
        // than the locale-formatted rendering so the check is stable
        // across CI runners with different default locales.
        expect(label_).toContain(timestamp);
      }),
      { numRuns: 100 },
    );
  });
});
