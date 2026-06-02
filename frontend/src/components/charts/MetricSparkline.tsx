interface MetricSparklineProps {
  color: string;
  label: string;
  points: number[];
  unit: string;
}

interface ChartCoordinate {
  x: number;
  y: number;
}

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

  return points
    .map((point, index) => {
      const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((point - min) / range) * (height - padding * 2);
      return { x, y };
    });
}

function buildPolyline(coordinates: ChartCoordinate[]): string {
  return coordinates.map((point) => `${point.x},${point.y}`).join(" ");
}

export function MetricSparkline({
  color,
  label,
  points,
  unit
}: MetricSparklineProps): JSX.Element {
  const width = 320;
  const height = 180;
  const padding = 16;
  const coordinates = buildCoordinates(points, width, height, padding);
  const polyline = buildPolyline(coordinates);
  const latest = points[points.length - 1];
  const latestCoordinate = coordinates[coordinates.length - 1];

  return (
    <article className="chart-card">
      <div className="chart-card__header">
        <div>
          <span className="fleet-card__eyebrow">Metric</span>
          <h3>{label}</h3>
        </div>
        <div className="chart-card__value">
          {latest !== undefined ? `${latest.toFixed(2)} ${unit}` : `No data ${unit}`}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart-card__svg"
        role="img"
        aria-label={`${label} trend`}
      >
        <rect x="0" y="0" width={width} height={height} rx="18" fill="rgba(10, 38, 44, 0.02)" />
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
