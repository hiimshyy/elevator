import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ElevatorSummary, listElevators } from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";

const refreshIntervalMs = 10_000;

function getStatusTone(elevator: ElevatorSummary): string {
  if (elevator.status === "CRITICAL" || elevator.status === "OVERLOAD") {
    return "status-badge status-badge--critical";
  }

  if (elevator.status === "WARNING") {
    return "status-badge status-badge--warning";
  }

  if ((elevator.latest_health_score ?? 100) >= 80) {
    return "status-badge status-badge--healthy";
  }

  if ((elevator.latest_health_score ?? 100) >= 50) {
    return "status-badge status-badge--warning";
  }

  return "status-badge status-badge--critical";
}

function formatHealthScore(score: number | null): string {
  return typeof score === "number" && Number.isFinite(score) ? `${score.toFixed(1)} / 100` : "N/A";
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function formatCapacity(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(0)} kg` : "N/A";
}

export function FleetOverviewPage(): JSX.Element {
  const { apiBaseUrl, apiKey } = useLocalConfig();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const load = async (signal?: AbortSignal): Promise<void> => {
      try {
        const nextElevators = await listElevators(signal);
        if (!isMounted) {
          return;
        }

        setElevators(nextElevators);
        setError(null);
        setLastUpdatedAt(new Date().toISOString());
      } catch (nextError) {
        if (!isMounted || signal?.aborted) {
          return;
        }

        setError(nextError instanceof Error ? nextError.message : "Unknown error");
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    const controller = new AbortController();
    void load(controller.signal);

    const intervalId = window.setInterval(() => {
      const intervalController = new AbortController();
      void load(intervalController.signal);
      window.setTimeout(() => intervalController.abort(), refreshIntervalMs - 1_000);
    }, refreshIntervalMs);

    return () => {
      isMounted = false;
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [apiBaseUrl, apiKey]);

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return "Loading fleet data";
    }

    if (error) {
      return "API request failed";
    }

    return `${elevators.length} elevator${elevators.length === 1 ? "" : "s"} loaded`;
  }, [elevators.length, error, isLoading]);

  return (
    <section className="page">
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Fleet Overview</h2>
        </div>
        <div className="status-pill">{summaryLabel}</div>
      </header>

      <div className="card-grid">
        <article className="card">
          <h3>Data source</h3>
          <p>
            Fleet data is loaded from <code>{apiBaseUrl}/elevators</code> and refreshed every{" "}
            {refreshIntervalMs / 1000} seconds.
          </p>
        </article>
        <article className="card">
          <h3>Last refresh</h3>
          <p>{lastUpdatedAt ? formatTimestamp(lastUpdatedAt) : "No successful refresh yet"}</p>
        </article>
      </div>

      {error ? <div className="callout callout--error">Unable to load fleet data. {error}</div> : null}

      {isLoading ? <div className="callout">Loading elevator summaries...</div> : null}

      {!isLoading && !error && elevators.length === 0 ? (
        <div className="callout">No elevators were returned by the API.</div>
      ) : null}

      {!isLoading && !error && elevators.length > 0 ? (
        <div className="fleet-grid">
          {elevators.map((elevator) => (
            <article key={elevator.id} className="fleet-card">
              <div className="fleet-card__header">
                <div>
                  <span className="fleet-card__eyebrow">Elevator</span>
                  <h3>{elevator.id}</h3>
                </div>
                <span className={getStatusTone(elevator)}>{elevator.status ?? "UNKNOWN"}</span>
              </div>

              <dl className="metric-list">
                <div>
                  <dt>Health score</dt>
                  <dd>{formatHealthScore(elevator.latest_health_score)}</dd>
                </div>
                <div>
                  <dt>Capacity</dt>
                  <dd>{formatCapacity(elevator.max_capacity_kg)}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatTimestamp(elevator.created_at)}</dd>
                </div>
              </dl>

              <Link className="button-link" to={`/live?elevator=${encodeURIComponent(elevator.id)}`}>
                Open Live Monitor
              </Link>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

