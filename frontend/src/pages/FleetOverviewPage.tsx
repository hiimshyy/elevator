import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PageContainer, ResponsiveGrid } from "../components/layout/PageContainer";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { mapElevatorStatusToState } from "../components/ui/statusState";
import { listElevators, type ElevatorSummary } from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";
import { useViewState } from "../lib/viewState";

// =============================================================================
// Fleet Overview route — refactored to consume the redesigned UI primitives.
//
// Requirements covered:
//   - 3.3 : presentation references Design_Token entries (via primitives that
//           are 100% token-driven) instead of hard-coded literals.
//   - 3.8 : route consumes the reusable Card / StatusBadge / Button / DataState
//           primitives provided by the Design_System.
//   - 4.1 : single-column layout at Mobile (PageContainer + ResponsiveGrid
//           derive their column count from useBreakpoint()'s descriptor).
//   - 4.2 : at most two columns at Tablet (same descriptor; tablet
//           columnCount = 2).
//   - 6.3 : every Status_Indicator (elevator status pill, top-of-page summary
//           pill) is rendered through StatusBadge, which conveys state with
//           color + icon + label + shape.
//   - 7.1 : loading indicator surfaced via DataState within 300ms — the
//           timing guarantee is owned by useViewState's loading-indicator
//           grace window.
//   - 7.3 : empty state names the missing data ("elevators") via DataState.
//   - 7.4 : error state names the view + reason and presents a Retry control
//           via DataState; prior data is preserved by useViewState's
//           failError transition.
//   - 7.8 : no internal endpoint URLs appear in this route — the legacy
//           "Data source" card that surfaced the API base URL has been
//           removed. Endpoint URLs are confined to the Local Config route.
// =============================================================================

/** Human-readable label used in announcements, error messages, and headings. */
const VIEW_LABEL = "Fleet Overview";

/** Periodic background-refresh interval, kept consistent with prior UX. */
const REFRESH_INTERVAL_MS = 10_000;

function formatHealthScore(score: number | null): string {
  return typeof score === "number" && Number.isFinite(score)
    ? `${score.toFixed(1)} / 100`
    : "N/A";
}

function formatTimestamp(value: string | null): string {
  if (value === null) {
    return "No successful refresh yet";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatCapacity(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(0)} kg` : "N/A";
}

/**
 * Derive the StatusBadge state for the page-level summary pill from the
 * current view-data state. Uses the canonical four-state mapper so the
 * summary pill differs by icon + label + shape (Req 6.3), not only color.
 */
function summaryBadgeState(
  state: "loading" | "empty" | "error" | "populated",
  hasPriorData: boolean,
): "healthy" | "warning" | "critical" | "unknown" {
  if (state === "error") {
    return hasPriorData ? "warning" : "critical";
  }
  if (state === "empty") {
    return "unknown";
  }
  if (state === "loading" && !hasPriorData) {
    return "unknown";
  }
  return "healthy";
}

function summaryBadgeLabel(
  state: "loading" | "empty" | "error" | "populated",
  count: number,
  hasPriorData: boolean,
): string {
  if (state === "loading" && !hasPriorData) {
    return "Loading fleet…";
  }
  if (state === "error" && !hasPriorData) {
    return "Fleet load failed";
  }
  if (state === "error") {
    return `Stale data (${count} elevator${count === 1 ? "" : "s"})`;
  }
  if (state === "empty") {
    return "No elevators registered";
  }
  return `${count} elevator${count === 1 ? "" : "s"} loaded`;
}

export function FleetOverviewPage(): JSX.Element {
  const { apiBaseUrl, apiKey } = useLocalConfig();
  const navigate = useNavigate();

  // Periodic background refresh — a tick state increments every
  // REFRESH_INTERVAL_MS and is included in useViewState's deps, which
  // re-runs the fetcher on each tick. The hook owns abort / supersede
  // semantics so the previous request is cancelled before each new one.
  const [refreshTick, setRefreshTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => {
      setRefreshTick((prev) => prev + 1);
    }, REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
    };
  }, []);

  const fleet = useViewState<ElevatorSummary[]>({
    viewLabel: VIEW_LABEL,
    fetcher: (signal) => listElevators(signal),
    isEmpty: (rows) => rows.length === 0,
    // apiBaseUrl / apiKey are part of deps so Local Config changes refresh
    // the view; refreshTick drives the periodic background refresh.
    deps: [apiBaseUrl, apiKey, refreshTick],
  });

  const elevators = fleet.data ?? [];
  const hasPriorData = elevators.length > 0;

  // -------------------------------------------------------------------------
  // Body branching — DataState owns loading / empty / error presentations
  // -------------------------------------------------------------------------
  let body: JSX.Element | null = null;

  if (fleet.state === "loading" && !hasPriorData) {
    // Suppress the spinner for sub-300ms requests via showLoadingIndicator,
    // which useViewState flips to true once the 300ms grace elapses
    // (Requirement 7.1).
    body = fleet.showLoadingIndicator ? (
      <DataState state="loading" viewLabel={VIEW_LABEL} />
    ) : null;
  } else if (fleet.state === "error" && !hasPriorData) {
    body = (
      <DataState
        state="error"
        viewLabel={VIEW_LABEL}
        errorReason={fleet.error ?? undefined}
        onRetry={fleet.retry}
      />
    );
  } else if (fleet.state === "empty") {
    // Requirement 7.3: empty state names the missing data noun.
    body = (
      <DataState
        state="empty"
        viewLabel={VIEW_LABEL}
        missingDataLabel="elevators"
      />
    );
  } else {
    // "populated", or "loading" / "error" with prior data preserved.
    body = (
      <>
        {/* Requirement 7.4: a failed refresh keeps the previously loaded
            cards visible and surfaces an error banner with a Retry control. */}
        {fleet.state === "error" ? (
          <DataState
            state="error"
            viewLabel={VIEW_LABEL}
            errorReason={fleet.error ?? undefined}
            onRetry={fleet.retry}
          />
        ) : null}

        <ResponsiveGrid aria-label="Elevator fleet">
          {elevators.map((elevator) => {
            const badgeState = mapElevatorStatusToState(
              elevator.status,
              elevator.latest_health_score,
            );

            return (
              <Card
                key={elevator.id}
                elevation="raised"
                header={
                  <>
                    <div>
                      <span className="page__eyebrow">Elevator</span>
                      <h3 className="ui-card__title">{elevator.id}</h3>
                    </div>
                    <StatusBadge state={badgeState} />
                  </>
                }
                footer={
                  <Button
                    variant="primary"
                    onClick={() =>
                      navigate(
                        `/live?elevator=${encodeURIComponent(elevator.id)}`,
                      )
                    }
                  >
                    Open Live Monitor
                  </Button>
                }
              >
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
              </Card>
            );
          })}
        </ResponsiveGrid>
      </>
    );
  }

  return (
    <PageContainer>
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Fleet Overview</h2>
        </div>
        <StatusBadge
          state={summaryBadgeState(fleet.state, hasPriorData)}
          labelOverride={summaryBadgeLabel(
            fleet.state,
            elevators.length,
            hasPriorData,
          )}
        />
      </header>

      {/* Top-of-page meta cards — limited to two columns so the row stays
          legible at Tablet and never exceeds Requirement 4.2's two-column
          cap. The "Data source" card that previously surfaced the API base
          URL has been removed to satisfy Requirement 7.8. */}
      <ResponsiveGrid maxColumns={2}>
        <Card title="Last refresh" headingLevel={3} elevation="flat">
          <p>{formatTimestamp(fleet.lastUpdatedAt)}</p>
        </Card>
        <Card title="Refresh cadence" headingLevel={3} elevation="flat">
          <p>
            Fleet data refreshes every {REFRESH_INTERVAL_MS / 1000} seconds.
          </p>
        </Card>
      </ResponsiveGrid>

      {body}
    </PageContainer>
  );
}
