import "./MetricSparkline.css";

// =============================================================================
// MetricSparkline — accessible SVG sparkline for the Live Monitor route.
//
// Requirements covered:
//   - 6.9 : the SVG exposes an accessible text alternative (role="img" +
//           aria-label + an in-DOM visually-hidden description) that
//           includes the latest value, the metric unit, and the
//           timestamp of the latest value.
//   - 7.6 : when the display series contains at least one interpolated
//           (synthetic) point, a persistent text label is rendered in the
//           chart header so synthetic data is always distinguished from
//           live packet data.
//   - 3.8 : chart card follows the redesigned primitive style (Card-like
//           surface). The .chart-card class rules remain in index.css;
//           new visuals reference design tokens via MetricSparkline.css.
//
// Non-requirements:
//   - Column layout of the chart grid at Mobile (Req 4.5) is owned by
//     LiveMonitorPage's ResponsiveGrid; this component only cares about
//     rendering one chart card.
//
// The component is intentionally dependency-free (no charting library)
// so the redesign does not expand the frontend's dependency surface.
// =============================================================================

/** Props accepted by {@link MetricSparkline}. */
export interface MetricSparklineProps {
  /** Stroke color for the trend polyline. Passed as a hex or token string. */
  color: string;
  /** Human-readable metric name (e.g. "Accel RMS"). */
  label: string;
  /** Value series to plot (oldest -> newest). */
  points: number[];
  /** Unit of measure for the metric (e.g. "mg", "mm/s", "kg", "C"). */
  unit: string;
  /**
   * Timestamp of the latest value in the series. When null / undefined, the
   * accessible text alternative reports "unknown timestamp" so it still
   * conveys the state to AT (Requirement 6.9).
   */
  latestTimestamp?: string | null;
  /**
   * True when the display series contains at least one interpolated
   * (synthetic) point. Drives the persistent "Interpolated trace" label in
   * the chart header (Requirement 7.6).
   */
  hasSyntheticPoints?: boolean;
}

interface ChartCoordinate {
  x: number;
  y: number;
}

/**
 * Compute the SVG coordinates for each data point. Kept as a pure helper
 * so it is straightforward to reason about — the transformation only
 * depends on its arguments.
 */
function buildCoordinates(
  points: number[],
  width: number,
  height: number,
  padding: number
): ChartCoordinate[] {
  if (points.length === 0) {
    return [];
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  return points.map((point, index) => {
    const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((point - min) / range) * (height - padding * 2);
    return { x, y };
  });
}

function buildPolyline(coordinates: ChartCoordinate[]): string {
  return coordinates.map((point) => `${point.x},${point.y}`).join(" ");
}

/**
 * Format an ISO timestamp for display in the accessible text alternative.
 * Falls back to a stable "unknown time" string when the timestamp is
 * missing or unparseable so the accessible label is never empty.
 */
function formatDisplayTimestamp(timestamp: string | null | undefined): string {
  if (timestamp === null || timestamp === undefined || timestamp.length === 0) {
    return "unknown time";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "unknown time";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

/**
 * Compose the accessible text alternative used by both `aria-label` and
 * the visually-hidden `<p>` description. Always includes the metric name,
 * the latest value, the unit, and the timestamp when data is present
 * (Requirement 6.9).
 *
 * Timestamps are surfaced twice — once as a human-formatted string and
 * once as the raw ISO string when available — so both human listeners and
 * automated checks can locate the timestamp reliably.
 */
export function buildChartAccessibleLabel(
  label: string,
  latestValue: number | null,
  unit: string,
  rawTimestamp: string | null | undefined
): string {
  if (latestValue === null || !Number.isFinite(latestValue)) {
    return `${label} chart. No data available.`;
  }
  const formatted = formatDisplayTimestamp(rawTimestamp);
  const rawSuffix =
    typeof rawTimestamp === "string" && rawTimestamp.length > 0 ? ` (${rawTimestamp})` : "";
  // Emit the raw numeric value with String(...) so property tests can
  // compare against the same value they generated without floating-point
  // formatting drift.
  return (
    `${label} chart. Latest value ${String(latestValue)} ${unit} at ` +
    `${formatted}${rawSuffix}.`
  );
}

/**
 * SVG sparkline chart card.
 *
 * Rendered structure:
 *   <article class="chart-card">
 *     <div class="chart-card__header">
 *       <h3>Label</h3>
 *       [optional synthetic-trace label]
 *       <span class="chart-card__value">latest value unit</span>
 *     </div>
 *     <p class="chart-card__sr-only">Accessible text alternative</p>
 *     <svg role="img" aria-label="Accessible text alternative">…</svg>
 *   </article>
 */
export function MetricSparkline({
  color,
  label,
  points,
  unit,
  latestTimestamp = null,
  hasSyntheticPoints = false,
}: MetricSparklineProps): JSX.Element {
  const width = 320;
  const height = 180;
  const padding = 16;

  const coordinates = buildCoordinates(points, width, height, padding);
  const polyline = buildPolyline(coordinates);
  const latest = points.length > 0 ? points[points.length - 1] : null;
  const latestCoordinate = coordinates[coordinates.length - 1];

  const accessibleLabel = buildChartAccessibleLabel(label, latest, unit, latestTimestamp);
  const visibleValue =
    latest !== null && Number.isFinite(latest) ? `${latest.toFixed(2)} ${unit}` : `No data ${unit}`;

  return (
    <article className="chart-card">
      <div className="chart-card__header">
        <div>
          <span className="fleet-card__eyebrow">Metric</span>
          <h3>{label}</h3>
        </div>
        {hasSyntheticPoints ? (
          // Requirement 7.6: persistent per-chart marker whenever the
          // rendered series contains any interpolated (synthetic) point.
          <span
            className="chart-card__synthetic-label"
            data-testid="metric-sparkline-synthetic-label"
          >
            <span aria-hidden="true">◈</span>
            Interpolated trace
          </span>
        ) : null}
        <div className="chart-card__value">{visibleValue}</div>
      </div>

      {/*
        Visually-hidden text alternative. Some assistive tech ignores the
        SVG's aria-label; a real in-DOM node guarantees the description is
        exposed (Requirement 6.9).
      */}
      <p
        className="chart-card__sr-only"
        data-testid="metric-sparkline-alt-text"
      >
        {accessibleLabel}
      </p>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart-card__svg"
        role="img"
        aria-label={accessibleLabel}
      >
        {/* Token-driven plot-area background (replaces the previous
            hard-coded rgba fill). */}
        <rect
          x="0"
          y="0"
          width={width}
          height={height}
          rx="18"
          className="chart-card__plot-bg"
        />
        {polyline ? (
          <>
            <polyline
              fill="none"
              stroke={color}
              strokeWidth="3"
              strokeLinejoin="round"
              strokeLinecap="round"
              points={polyline}
            />
            {latestCoordinate ? (
              <>
                <circle
                  className="chart-card__pulse"
                  cx={latestCoordinate.x}
                  cy={latestCoordinate.y}
                  fill={color}
                  r="12"
                />
                <circle cx={latestCoordinate.x} cy={latestCoordinate.y} fill={color} r="4.5" />
              </>
            ) : null}
          </>
        ) : null}
      </svg>
    </article>
  );
}
