// Feature: ui-ux-responsive-redesign, Property 12: Synthetic telemetry is always labeled when present
//
// Validates: Requirements 7.6
//
// Property 12 (from design.md):
//   For all display point sets that contain at least one interpolated
//   (synthetic) point, the Live_Telemetry_View renders a persistent label
//   distinguishing synthetic data from live packet data.
//
// Requirement 7.6 (from requirements.md):
//   WHILE the Live_Telemetry_View renders an interpolated synthetic trace,
//   THE Live_Telemetry_View SHALL display a persistent text label that
//   distinguishes synthetic data from live packet data.
//
// Test strategy
// -------------
// `MetricSparkline` (frontend/src/components/charts/MetricSparkline.tsx)
// receives a `hasSyntheticPoints` boolean prop derived from the display
// point set. When any point in the display set carries `source ===
// "synthetic"`, the Live Monitor computes `hasSyntheticPoints = true` and
// forwards it to the sparkline, which renders a persistent header label
// (identified by `data-testid="metric-sparkline-synthetic-label"`).
//
// The property is bi-conditional: the label MUST be present whenever the
// series contains a synthetic point, and MUST NOT be present when the
// series is entirely live/actual data. We therefore universally quantify
// over arbitrary display point sets (each point tagged with an "actual"
// or "synthetic" source) and assert both directions in one iteration.

import { cleanup, render } from "@testing-library/react";
import * as fc from "fast-check";
import { afterEach, describe, expect, it } from "vitest";

import { MetricSparkline } from "./MetricSparkline";

afterEach(() => {
  // Each fast-check iteration mounts a fresh MetricSparkline; without an
  // explicit cleanup the previous render's DOM would leak into the next
  // iteration's document-level testid queries.
  cleanup();
});

/**
 * A single display point mirrors the shape used by `LiveMonitorPage`'s
 * `LivePoint`: a numeric value plus a `source` tag that distinguishes
 * live packet data ("actual") from interpolated data ("synthetic").
 */
const arbDisplayPoint = fc.record({
  source: fc.constantFrom("actual" as const, "synthetic" as const),
  value: fc.float({ noNaN: true, min: -1_000, max: 1_000 }),
});

/**
 * Bounded to 60 points to match `MAX_POINTS` in `LiveMonitorPage` — this
 * is the realistic input space the sparkline ever renders.
 */
const arbDisplayPoints = fc.array(arbDisplayPoint, { minLength: 1, maxLength: 60 });

describe("Property 12: Synthetic telemetry is always labeled when present (Requirement 7.6)", () => {
  it("renders the persistent synthetic label iff any display point is synthetic", () => {
    fc.assert(
      fc.property(arbDisplayPoints, (displayPoints) => {
        cleanup();

        const hasSyntheticPoints = displayPoints.some(
          (point) => point.source === "synthetic"
        );
        const numericSeries = displayPoints.map((point) => point.value);

        const { container } = render(
          <MetricSparkline
            color="#00ff88"
            label="Accel RMS"
            points={numericSeries}
            unit="mg"
            latestTimestamp="2024-01-01T00:00:00Z"
            hasSyntheticPoints={hasSyntheticPoints}
          />
        );

        const syntheticLabel = container.querySelector(
          '[data-testid="metric-sparkline-synthetic-label"]'
        );

        if (hasSyntheticPoints) {
          // Forward direction: any synthetic point -> label MUST appear so
          // the operator can distinguish interpolated data from live data
          // (Requirement 7.6).
          expect(syntheticLabel).not.toBeNull();
          expect(syntheticLabel!.textContent ?? "").toContain("Interpolated");
        } else {
          // Reverse direction: no synthetic points -> the label MUST NOT
          // be shown. A permanently-visible label would mislead the
          // operator into thinking live data is interpolated.
          expect(syntheticLabel).toBeNull();
        }
      }),
      { numRuns: 100 }
    );
  });
});
