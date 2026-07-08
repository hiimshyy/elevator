import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { PageContainer, ResponsiveGrid } from "../components/layout/PageContainer";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { Select, Textarea, TextInput } from "../components/ui/Field";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  mapAlertSeverityToState,
  mapMaintenanceStatusToState,
} from "../components/ui/statusState";
import {
  AlertRecord,
  ElevatorSummary,
  MaintenanceRecord,
  acknowledgeAlert,
  createMaintenance,
  listAlerts,
  listElevators,
  listMaintenance,
  updateMaintenance,
} from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";
import { useViewState } from "../lib/viewState";

// =============================================================================
// Alerts & Maintenance route — refactored to consume redesigned UI primitives.
//
// Requirements covered:
//   - 3.3 : presentation references Design_Token entries (via primitives that
//           are 100% token-driven) instead of hard-coded literals.
//   - 3.8 : route consumes the reusable Card / StatusBadge / Button / DataState
//           / Select / TextInput / Textarea primitives.
//   - 4.1 : single-column layout at Mobile (PageContainer + ResponsiveGrid
//           derive column count from useBreakpoint()'s descriptor).
//   - 4.2 : at most two columns at Tablet (same descriptor; tablet
//           columnCount = 2).
//   - 6.3 : every Status_Indicator (alert severity badge, maintenance status
//           badge, summary pill) is rendered through StatusBadge, which conveys
//           state with color + icon + label + shape.
//   - 7.1 : loading indicator surfaced via DataState within 300ms — timing
//           guarantee owned by useViewState's loading-indicator grace window.
//   - 7.3 : empty state names the missing data via DataState.
//   - 7.4 : error state names the view + reason and presents a Retry control
//           via DataState; prior data preserved by useViewState's failError
//           transition.
//   - 7.8 : no internal endpoint URLs appear in this route — the legacy
//           meta lines that surfaced the API base URL have been removed.
//           Endpoint URLs are confined to the Local Config route.
// =============================================================================

/** Human-readable label used in error messages and headings. */
const VIEW_LABEL = "Alerts & Maintenance";

const urgencyOptions = ["routine", "soon", "urgent", "immediate"] as const;
const maintenanceStatusOptions = ["pending", "scheduled", "completed", "cancelled"] as const;
const severityOptions = ["WARNING", "CRITICAL", "EMERGENCY"] as const;

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "N/A";
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

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(date);
}

function getDefaultRecommendedDate(): string {
  const nextWeek = new Date();
  nextWeek.setDate(nextWeek.getDate() + 7);
  return nextWeek.toISOString().slice(0, 10);
}

/** Derive the summary pill state from the view-data state. */
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
  alertCount: number,
  maintenanceCount: number,
  hasPriorData: boolean,
): string {
  if (state === "loading" && !hasPriorData) {
    return "Loading workflows…";
  }
  if (state === "error" && !hasPriorData) {
    return "Load failed";
  }
  if (state === "error") {
    return `Stale data (${alertCount} alerts / ${maintenanceCount} tasks)`;
  }
  if (state === "empty") {
    return "No alerts or maintenance";
  }
  return `${alertCount} alerts / ${maintenanceCount} tasks`;
}

interface AlertsMaintenanceData {
  alerts: AlertRecord[];
  maintenance: MaintenanceRecord[];
}

export function AlertsMaintenancePage(): JSX.Element {
  const { apiBaseUrl, apiKey } = useLocalConfig();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [selectedElevator, setSelectedElevator] = useState("all");
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [selectedMaintenanceStatus, setSelectedMaintenanceStatus] = useState("all");
  const [includeAcknowledged, setIncludeAcknowledged] = useState(true);
  const [technicianName, setTechnicianName] = useState("ops-01");
  const [busyAlertId, setBusyAlertId] = useState<number | null>(null);
  const [busyMaintenanceId, setBusyMaintenanceId] = useState<number | null>(null);
  const [isCreatingMaintenance, setIsCreatingMaintenance] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [maintenanceDraft, setMaintenanceDraft] = useState({
    elevatorId: "",
    recommendedDate: getDefaultRecommendedDate(),
    urgency: "soon",
    reason: "",
  });

  // -------------------------------------------------------------------------
  // Load elevator options for dropdown (separate lifecycle from main data)
  // -------------------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();

    const loadElevatorOptions = async (): Promise<void> => {
      try {
        const nextElevators = await listElevators(controller.signal);
        setElevators(nextElevators);
        setMaintenanceDraft((current) => ({
          ...current,
          elevatorId: current.elevatorId || nextElevators[0]?.id || "",
        }));
      } catch (nextError) {
        if (!controller.signal.aborted) {
          setActionError(
            nextError instanceof Error ? nextError.message : "Unable to load elevators",
          );
        }
      }
    };

    void loadElevatorOptions();

    return () => controller.abort();
  }, [apiBaseUrl, apiKey]);

  // -------------------------------------------------------------------------
  // Main data lifecycle via useViewState (alerts + maintenance combined)
  // -------------------------------------------------------------------------
  const view = useViewState<AlertsMaintenanceData>({
    viewLabel: VIEW_LABEL,
    fetcher: async (signal) => {
      const elevatorFilter = selectedElevator === "all" ? undefined : selectedElevator;
      const severityFilter = selectedSeverity === "all" ? undefined : selectedSeverity;
      const maintenanceStatusFilter =
        selectedMaintenanceStatus === "all" ? undefined : selectedMaintenanceStatus;
      const acknowledgedFilter = includeAcknowledged ? undefined : false;

      const [nextAlerts, nextMaintenance] = await Promise.all([
        listAlerts(
          {
            elevatorId: elevatorFilter,
            severity: severityFilter,
            acknowledged: acknowledgedFilter,
          },
          signal,
        ),
        listMaintenance(
          {
            elevatorId: elevatorFilter,
            status: maintenanceStatusFilter,
          },
          signal,
        ),
      ]);

      return { alerts: nextAlerts, maintenance: nextMaintenance };
    },
    isEmpty: (data) => data.alerts.length === 0 && data.maintenance.length === 0,
    deps: [
      apiBaseUrl,
      apiKey,
      selectedElevator,
      selectedSeverity,
      selectedMaintenanceStatus,
      includeAcknowledged,
    ],
  });

  const alerts = view.data?.alerts ?? [];
  const maintenance = view.data?.maintenance ?? [];
  const hasPriorData = alerts.length > 0 || maintenance.length > 0;

  const openAlerts = useMemo(
    () => alerts.filter((alert) => alert.acknowledged === 0).length,
    [alerts],
  );
  const criticalAlerts = useMemo(
    () => alerts.filter((alert) => alert.severity !== "WARNING" && alert.acknowledged === 0).length,
    [alerts],
  );
  const pendingMaintenance = useMemo(
    () => maintenance.filter((record) => record.status === "pending").length,
    [maintenance],
  );
  const scheduledMaintenance = useMemo(
    () => maintenance.filter((record) => record.status === "scheduled").length,
    [maintenance],
  );

  // -------------------------------------------------------------------------
  // Reload helper (for actions that mutate data and need to refresh)
  // -------------------------------------------------------------------------
  const reloadData = useCallback(() => {
    view.retry();
  }, [view]);

  // -------------------------------------------------------------------------
  // Action handlers
  // -------------------------------------------------------------------------
  const handleAcknowledge = async (alertId: number | null): Promise<void> => {
    if (alertId === null) {
      return;
    }

    const technician = technicianName.trim();
    if (!technician) {
      setActionError("Technician name is required to acknowledge an alert.");
      return;
    }

    try {
      setBusyAlertId(alertId);
      setActionError(null);
      await acknowledgeAlert(alertId, technician);
      reloadData();
    } catch (nextError) {
      setActionError(nextError instanceof Error ? nextError.message : "Unable to acknowledge alert");
    } finally {
      setBusyAlertId(null);
    }
  };

  const handleMaintenanceSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    if (!maintenanceDraft.elevatorId || !maintenanceDraft.reason.trim()) {
      setActionError("Maintenance requires an elevator and a reason.");
      return;
    }

    try {
      setIsCreatingMaintenance(true);
      setActionError(null);
      await createMaintenance({
        elevator_id: maintenanceDraft.elevatorId,
        recommended_date: maintenanceDraft.recommendedDate,
        urgency: maintenanceDraft.urgency,
        reason: maintenanceDraft.reason.trim(),
      });
      setMaintenanceDraft((current) => ({
        ...current,
        reason: "",
        recommendedDate: getDefaultRecommendedDate(),
      }));
      reloadData();
    } catch (nextError) {
      setActionError(nextError instanceof Error ? nextError.message : "Unable to create maintenance");
    } finally {
      setIsCreatingMaintenance(false);
    }
  };

  const handleMaintenanceStatus = async (
    maintenanceId: number | null,
    status: string,
  ): Promise<void> => {
    if (maintenanceId === null) {
      return;
    }

    const technician = technicianName.trim();

    try {
      setBusyMaintenanceId(maintenanceId);
      setActionError(null);
      await updateMaintenance(maintenanceId, {
        status,
        technician: technician || undefined,
        completedAt: status === "completed" ? new Date().toISOString() : undefined,
      });
      reloadData();
    } catch (nextError) {
      setActionError(
        nextError instanceof Error ? nextError.message : "Unable to update maintenance",
      );
    } finally {
      setBusyMaintenanceId(null);
    }
  };

  // -------------------------------------------------------------------------
  // Select options built from constants
  // -------------------------------------------------------------------------
  const elevatorSelectOptions = [
    { value: "all", label: "All elevators" },
    ...elevators.map((e) => ({ value: e.id, label: e.id })),
  ];

  const severitySelectOptions = [
    { value: "all", label: "All severities" },
    ...severityOptions.map((s) => ({ value: s, label: s })),
  ];

  const maintenanceStatusSelectOptions = [
    { value: "all", label: "All statuses" },
    ...maintenanceStatusOptions.map((s) => ({ value: s, label: s })),
  ];

  const urgencySelectOptions = urgencyOptions.map((u) => ({ value: u, label: u }));

  const elevatorFormOptions = elevators.map((e) => ({ value: e.id, label: e.id }));

  // -------------------------------------------------------------------------
  // Body branching — DataState owns loading / empty / error presentations
  // -------------------------------------------------------------------------
  let body: JSX.Element | null = null;

  if (view.state === "loading" && !hasPriorData) {
    body = view.showLoadingIndicator ? (
      <DataState state="loading" viewLabel={VIEW_LABEL} />
    ) : null;
  } else if (view.state === "error" && !hasPriorData) {
    body = (
      <DataState
        state="error"
        viewLabel={VIEW_LABEL}
        errorReason={view.error ?? undefined}
        onRetry={view.retry}
      />
    );
  } else if (view.state === "empty") {
    body = (
      <DataState
        state="empty"
        viewLabel={VIEW_LABEL}
        missingDataLabel="alerts or maintenance records"
      />
    );
  } else {
    // "populated", or "loading" / "error" with prior data preserved.
    body = (
      <>
        {view.state === "error" ? (
          <DataState
            state="error"
            viewLabel={VIEW_LABEL}
            errorReason={view.error ?? undefined}
            onRetry={view.retry}
          />
        ) : null}

        <ResponsiveGrid maxColumns={2}>
          {/* Alerts Inbox Panel */}
          <Card
            elevation="raised"
            headingLevel={3}
            header={
              <>
                <div>
                  <span className="page__eyebrow">Workflow</span>
                  <h3 className="ui-card__title">Alerts Inbox</h3>
                </div>
                <StatusBadge
                  state={openAlerts > 0 ? "warning" : "healthy"}
                  labelOverride={`${openAlerts} open`}
                />
              </>
            }
          >
            {alerts.length === 0 ? (
              <DataState
                state="empty"
                viewLabel="Alerts"
                missingDataLabel="alerts matching the current filter"
              />
            ) : (
              <div className="stack">
                {alerts.map((alert) => {
                  const isBusy = busyAlertId === alert.id;
                  const isAcknowledged = alert.acknowledged !== 0;

                  return (
                    <Card
                      key={`${alert.id}-${alert.timestamp}`}
                      elevation="flat"
                      headingLevel={4}
                      header={
                        <>
                          <div>
                            <span className="page__eyebrow">{alert.elevator_id}</span>
                            <h4 className="ui-card__title">{alert.message}</h4>
                          </div>
                          <StatusBadge state={mapAlertSeverityToState(alert.severity)} />
                        </>
                      }
                    >
                      <dl className="metric-list">
                        <div>
                          <dt>Raised</dt>
                          <dd>{formatTimestamp(alert.timestamp)}</dd>
                        </div>
                        <div>
                          <dt>Status</dt>
                          <dd>{isAcknowledged ? "Acknowledged" : "Awaiting action"}</dd>
                        </div>
                      </dl>

                      {isAcknowledged ? (
                        <p>
                          Acknowledged by <strong>{alert.acknowledged_by ?? "Unknown"}</strong> at{" "}
                          <strong>{formatTimestamp(alert.acknowledged_at)}</strong>.
                        </p>
                      ) : (
                        <Button
                          variant="primary"
                          disabled={isBusy}
                          onClick={() => void handleAcknowledge(alert.id)}
                        >
                          {isBusy ? "Acknowledging…" : "Acknowledge alert"}
                        </Button>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Maintenance Board Panel */}
          <Card
            elevation="raised"
            headingLevel={3}
            header={
              <>
                <div>
                  <span className="page__eyebrow">Workflow</span>
                  <h3 className="ui-card__title">Maintenance Board</h3>
                </div>
                <StatusBadge
                  state={pendingMaintenance > 0 ? "warning" : "healthy"}
                  labelOverride={`${maintenance.length} records`}
                />
              </>
            }
          >
            <form
              className="maintenance-form"
              onSubmit={(event) => void handleMaintenanceSubmit(event)}
              style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
            >
              <ResponsiveGrid maxColumns={3}>
                <Select
                  label="Elevator"
                  value={maintenanceDraft.elevatorId}
                  options={elevatorFormOptions}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      elevatorId: event.target.value,
                    }))
                  }
                />

                <TextInput
                  label="Recommended date"
                  type="text"
                  value={maintenanceDraft.recommendedDate}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      recommendedDate: event.target.value,
                    }))
                  }
                  placeholder="YYYY-MM-DD"
                />

                <Select
                  label="Urgency"
                  value={maintenanceDraft.urgency}
                  options={urgencySelectOptions}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      urgency: event.target.value,
                    }))
                  }
                />
              </ResponsiveGrid>

              <Textarea
                label="Reason"
                rows={3}
                value={maintenanceDraft.reason}
                onChange={(event) =>
                  setMaintenanceDraft((current) => ({
                    ...current,
                    reason: event.target.value,
                  }))
                }
                placeholder="Describe why this maintenance task is needed"
              />

              <Button variant="primary" type="submit" disabled={isCreatingMaintenance}>
                {isCreatingMaintenance ? "Creating…" : "Create maintenance task"}
              </Button>
            </form>

            {maintenance.length === 0 ? (
              <DataState
                state="empty"
                viewLabel="Maintenance"
                missingDataLabel="maintenance records matching the current filter"
              />
            ) : (
              <div className="stack">
                {maintenance.map((record) => {
                  const isBusy = busyMaintenanceId === record.id;

                  return (
                    <Card
                      key={`${record.id}-${record.created_at}`}
                      elevation="flat"
                      headingLevel={4}
                      header={
                        <>
                          <div>
                            <span className="page__eyebrow">{record.elevator_id}</span>
                            <h4 className="ui-card__title">{record.reason}</h4>
                          </div>
                          <StatusBadge state={mapMaintenanceStatusToState(record.status)} />
                        </>
                      }
                      footer={
                        <div className="action-row">
                          {record.status !== "scheduled" ? (
                            <Button
                              variant="secondary"
                              disabled={isBusy}
                              onClick={() => void handleMaintenanceStatus(record.id, "scheduled")}
                            >
                              Schedule
                            </Button>
                          ) : null}

                          {record.status !== "completed" ? (
                            <Button
                              variant="primary"
                              disabled={isBusy}
                              onClick={() => void handleMaintenanceStatus(record.id, "completed")}
                            >
                              Complete
                            </Button>
                          ) : null}

                          {record.status !== "cancelled" ? (
                            <Button
                              variant="ghost"
                              disabled={isBusy}
                              onClick={() => void handleMaintenanceStatus(record.id, "cancelled")}
                            >
                              Cancel
                            </Button>
                          ) : null}
                        </div>
                      }
                    >
                      <dl className="metric-list">
                        <div>
                          <dt>Recommended</dt>
                          <dd>{formatDate(record.recommended_date)}</dd>
                        </div>
                        <div>
                          <dt>Urgency</dt>
                          <dd>{record.urgency}</dd>
                        </div>
                        <div>
                          <dt>Created</dt>
                          <dd>{formatTimestamp(record.created_at)}</dd>
                        </div>
                        <div>
                          <dt>Technician</dt>
                          <dd>{record.technician ?? "Unassigned"}</dd>
                        </div>
                      </dl>
                    </Card>
                  );
                })}
              </div>
            )}
          </Card>
        </ResponsiveGrid>
      </>
    );
  }

  return (
    <PageContainer>
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Alerts &amp; Maintenance</h2>
        </div>
        <StatusBadge
          state={summaryBadgeState(view.state, hasPriorData)}
          labelOverride={summaryBadgeLabel(
            view.state,
            alerts.length,
            maintenance.length,
            hasPriorData,
          )}
        />
      </header>

      {/* Summary cards strip */}
      <ResponsiveGrid maxColumns={4}>
        <Card title="Open alerts" headingLevel={3} elevation="flat">
          <strong>{openAlerts}</strong>
        </Card>
        <Card title="Critical or emergency" headingLevel={3} elevation="flat">
          <strong>{criticalAlerts}</strong>
        </Card>
        <Card title="Pending maintenance" headingLevel={3} elevation="flat">
          <strong>{pendingMaintenance}</strong>
        </Card>
        <Card title="Scheduled maintenance" headingLevel={3} elevation="flat">
          <strong>{scheduledMaintenance}</strong>
        </Card>
      </ResponsiveGrid>

      {/* Filter toolbar */}
      <Card title="Filters" headingLevel={3} elevation="flat">
        <ResponsiveGrid maxColumns={4}>
          <Select
            label="Elevator scope"
            value={selectedElevator}
            options={elevatorSelectOptions}
            onChange={(event) => setSelectedElevator(event.target.value)}
          />

          <Select
            label="Alert severity"
            value={selectedSeverity}
            options={severitySelectOptions}
            onChange={(event) => setSelectedSeverity(event.target.value)}
          />

          <Select
            label="Maintenance status"
            value={selectedMaintenanceStatus}
            options={maintenanceStatusSelectOptions}
            onChange={(event) => setSelectedMaintenanceStatus(event.target.value)}
          />

          <TextInput
            label="Technician"
            value={technicianName}
            onChange={(event) => setTechnicianName(event.target.value)}
            placeholder="ops-01"
          />
        </ResponsiveGrid>

        <div className="toolbar__meta toolbar__meta--inline">
          <label className="checkbox">
            <input
              checked={includeAcknowledged}
              onChange={(event) => setIncludeAcknowledged(event.target.checked)}
              type="checkbox"
            />
            <span>Include acknowledged alerts</span>
          </label>
          <span>
            {view.lastUpdatedAt
              ? `Last refresh: ${formatTimestamp(view.lastUpdatedAt)}`
              : "No refresh yet"}
          </span>
        </div>
      </Card>

      {/* Action error banner */}
      {actionError ? (
        <div className="callout callout--error" role="alert">{actionError}</div>
      ) : null}

      {body}
    </PageContainer>
  );
}
