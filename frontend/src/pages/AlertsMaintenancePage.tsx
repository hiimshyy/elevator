import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  AlertRecord,
  ElevatorSummary,
  MaintenanceRecord,
  acknowledgeAlert,
  createMaintenance,
  listAlerts,
  listElevators,
  listMaintenance,
  updateMaintenance
} from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";

const urgencyOptions = ["routine", "soon", "urgent", "immediate"] as const;
const maintenanceStatusOptions = ["pending", "scheduled", "completed", "cancelled"] as const;
const severityOptions = ["WARNING", "CRITICAL", "EMERGENCY"] as const;

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium"
  }).format(new Date(value));
}

function getAlertTone(alert: AlertRecord): string {
  if (alert.severity === "EMERGENCY") {
    return "status-badge status-badge--critical";
  }

  if (alert.severity === "CRITICAL") {
    return "status-badge status-badge--warning";
  }

  return "status-badge status-badge--healthy";
}

function getMaintenanceTone(record: MaintenanceRecord): string {
  if (record.status === "completed") {
    return "status-badge status-badge--healthy";
  }

  if (record.status === "cancelled") {
    return "status-badge status-badge--critical";
  }

  if (record.status === "scheduled") {
    return "status-badge status-badge--warning";
  }

  return "status-badge";
}

function getDefaultRecommendedDate(): string {
  const nextWeek = new Date();
  nextWeek.setDate(nextWeek.getDate() + 7);
  return nextWeek.toISOString().slice(0, 10);
}

export function AlertsMaintenancePage(): JSX.Element {
  const { apiBaseUrl, apiKey } = useLocalConfig();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [maintenance, setMaintenance] = useState<MaintenanceRecord[]>([]);
  const [selectedElevator, setSelectedElevator] = useState("all");
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [selectedMaintenanceStatus, setSelectedMaintenanceStatus] = useState("all");
  const [includeAcknowledged, setIncludeAcknowledged] = useState(true);
  const [technicianName, setTechnicianName] = useState("ops-01");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyAlertId, setBusyAlertId] = useState<number | null>(null);
  const [busyMaintenanceId, setBusyMaintenanceId] = useState<number | null>(null);
  const [isCreatingMaintenance, setIsCreatingMaintenance] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [maintenanceDraft, setMaintenanceDraft] = useState({
    elevatorId: "",
    recommendedDate: getDefaultRecommendedDate(),
    urgency: "soon",
    reason: ""
  });

  const loadData = useCallback(
    async (signal?: AbortSignal): Promise<void> => {
      const elevatorFilter = selectedElevator === "all" ? undefined : selectedElevator;
      const severityFilter = selectedSeverity === "all" ? undefined : selectedSeverity;
      const maintenanceStatusFilter =
        selectedMaintenanceStatus === "all" ? undefined : selectedMaintenanceStatus;
      const acknowledgedFilter = includeAcknowledged ? undefined : false;

      try {
        const [nextAlerts, nextMaintenance] = await Promise.all([
          listAlerts(
            {
              elevatorId: elevatorFilter,
              severity: severityFilter,
              acknowledged: acknowledgedFilter
            },
            signal
          ),
          listMaintenance(
            {
              elevatorId: elevatorFilter,
              status: maintenanceStatusFilter
            },
            signal
          )
        ]);

        setAlerts(nextAlerts);
        setMaintenance(nextMaintenance);
        setError(null);
        setLastUpdatedAt(new Date().toISOString());
      } catch (nextError) {
        if (!signal?.aborted) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load operations data");
        }
      } finally {
        if (!signal?.aborted) {
          setIsLoading(false);
        }
      }
    },
    [includeAcknowledged, selectedElevator, selectedMaintenanceStatus, selectedSeverity]
  );

  useEffect(() => {
    const controller = new AbortController();

    const loadElevatorOptions = async (): Promise<void> => {
      try {
        const nextElevators = await listElevators(controller.signal);
        setElevators(nextElevators);
        setMaintenanceDraft((current) => ({
          ...current,
          elevatorId: current.elevatorId || nextElevators[0]?.id || ""
        }));
      } catch (nextError) {
        if (!controller.signal.aborted) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load elevators");
          setIsLoading(false);
        }
      }
    };

    void loadElevatorOptions();

    return () => controller.abort();
  }, [apiBaseUrl, apiKey]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    void loadData(controller.signal);
    return () => controller.abort();
  }, [apiBaseUrl, apiKey, loadData]);

  const openAlerts = useMemo(
    () => alerts.filter((alert) => alert.acknowledged === 0).length,
    [alerts]
  );
  const criticalAlerts = useMemo(
    () => alerts.filter((alert) => alert.severity !== "WARNING" && alert.acknowledged === 0).length,
    [alerts]
  );
  const pendingMaintenance = useMemo(
    () => maintenance.filter((record) => record.status === "pending").length,
    [maintenance]
  );
  const scheduledMaintenance = useMemo(
    () => maintenance.filter((record) => record.status === "scheduled").length,
    [maintenance]
  );

  const handleAcknowledge = async (alertId: number | null): Promise<void> => {
    if (alertId === null) {
      return;
    }

    const technician = technicianName.trim();
    if (!technician) {
      setError("Technician name is required to acknowledge an alert.");
      return;
    }

    try {
      setBusyAlertId(alertId);
      await acknowledgeAlert(alertId, technician);
      await loadData();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to acknowledge alert");
    } finally {
      setBusyAlertId(null);
    }
  };

  const handleMaintenanceSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    if (!maintenanceDraft.elevatorId || !maintenanceDraft.reason.trim()) {
      setError("Maintenance requires an elevator and a reason.");
      return;
    }

    try {
      setIsCreatingMaintenance(true);
      await createMaintenance({
        elevator_id: maintenanceDraft.elevatorId,
        recommended_date: maintenanceDraft.recommendedDate,
        urgency: maintenanceDraft.urgency,
        reason: maintenanceDraft.reason.trim()
      });
      setMaintenanceDraft((current) => ({
        ...current,
        reason: "",
        recommendedDate: getDefaultRecommendedDate()
      }));
      await loadData();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to create maintenance");
    } finally {
      setIsCreatingMaintenance(false);
    }
  };

  const handleMaintenanceStatus = async (
    maintenanceId: number | null,
    status: string
  ): Promise<void> => {
    if (maintenanceId === null) {
      return;
    }

    const technician = technicianName.trim();

    try {
      setBusyMaintenanceId(maintenanceId);
      await updateMaintenance(maintenanceId, {
        status,
        technician: technician || undefined,
        completedAt: status === "completed" ? new Date().toISOString() : undefined
      });
      await loadData();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to update maintenance");
    } finally {
      setBusyMaintenanceId(null);
    }
  };

  return (
    <section className="page">
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Alerts & Maintenance</h2>
        </div>
        <div className="status-pill">
          {isLoading ? "Loading workflows" : `${alerts.length} alerts / ${maintenance.length} tasks`}
        </div>
      </header>

      <div className="toolbar">
        <div className="toolbar__fields">
          <label className="field">
            <span>Elevator scope</span>
            <select
              value={selectedElevator}
              onChange={(event) => setSelectedElevator(event.target.value)}
            >
              <option value="all">All elevators</option>
              {elevators.map((elevator) => (
                <option key={elevator.id} value={elevator.id}>
                  {elevator.id}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Alert severity</span>
            <select
              value={selectedSeverity}
              onChange={(event) => setSelectedSeverity(event.target.value)}
            >
              <option value="all">All severities</option>
              {severityOptions.map((severity) => (
                <option key={severity} value={severity}>
                  {severity}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Maintenance status</span>
            <select
              value={selectedMaintenanceStatus}
              onChange={(event) => setSelectedMaintenanceStatus(event.target.value)}
            >
              <option value="all">All statuses</option>
              {maintenanceStatusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Technician</span>
            <input
              value={technicianName}
              onChange={(event) => setTechnicianName(event.target.value)}
              placeholder="ops-01"
              type="text"
            />
          </label>
        </div>

        <div className="toolbar__meta toolbar__meta--inline">
          <span>Alerts: {apiBaseUrl}/alerts</span>
          <span>Maintenance: {apiBaseUrl}/maintenance</span>
          <label className="checkbox">
            <input
              checked={includeAcknowledged}
              onChange={(event) => setIncludeAcknowledged(event.target.checked)}
              type="checkbox"
            />
            <span>Include acknowledged alerts</span>
          </label>
          <span>{lastUpdatedAt ? `Last refresh: ${formatTimestamp(lastUpdatedAt)}` : "No refresh yet"}</span>
        </div>
      </div>

      <div className="summary-strip">
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Open alerts</span>
          <strong>{openAlerts}</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Critical or emergency</span>
          <strong>{criticalAlerts}</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Pending maintenance</span>
          <strong>{pendingMaintenance}</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Scheduled maintenance</span>
          <strong>{scheduledMaintenance}</strong>
        </article>
      </div>

      {error ? <div className="callout callout--error">{error}</div> : null}

      {isLoading ? <div className="callout">Loading alerts and maintenance workflows...</div> : null}

      <div className="operations-grid">
        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="fleet-card__eyebrow">Workflow</span>
              <h3>Alerts Inbox</h3>
            </div>
            <span className="status-pill">{openAlerts} open</span>
          </div>

          {!isLoading && alerts.length === 0 ? (
            <div className="callout">No alerts matched the current filter set.</div>
          ) : (
            <div className="stack">
              {alerts.map((alert) => {
                const isBusy = busyAlertId === alert.id;
                const isAcknowledged = alert.acknowledged !== 0;

                return (
                  <article key={`${alert.id}-${alert.timestamp}`} className="workflow-card">
                    <div className="workflow-card__header">
                      <div>
                        <span className="fleet-card__eyebrow">{alert.elevator_id}</span>
                        <h4>{alert.message}</h4>
                      </div>
                      <span className={getAlertTone(alert)}>{alert.severity}</span>
                    </div>

                    <dl className="workflow-card__meta">
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
                      <div className="callout">
                        Acknowledged by <strong>{alert.acknowledged_by ?? "Unknown"}</strong> at{" "}
                        <strong>{formatTimestamp(alert.acknowledged_at)}</strong>.
                      </div>
                    ) : (
                      <button
                        className="action-button"
                        disabled={isBusy}
                        onClick={() => void handleAcknowledge(alert.id)}
                        type="button"
                      >
                        {isBusy ? "Acknowledging..." : "Acknowledge alert"}
                      </button>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="fleet-card__eyebrow">Workflow</span>
              <h3>Maintenance Board</h3>
            </div>
            <span className="status-pill">{maintenance.length} records</span>
          </div>

          <form className="maintenance-form" onSubmit={(event) => void handleMaintenanceSubmit(event)}>
            <div className="form-grid">
              <label className="field">
                <span>Elevator</span>
                <select
                  value={maintenanceDraft.elevatorId}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      elevatorId: event.target.value
                    }))
                  }
                >
                  {elevators.map((elevator) => (
                    <option key={elevator.id} value={elevator.id}>
                      {elevator.id}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Recommended date</span>
                <input
                  type="date"
                  value={maintenanceDraft.recommendedDate}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      recommendedDate: event.target.value
                    }))
                  }
                />
              </label>

              <label className="field">
                <span>Urgency</span>
                <select
                  value={maintenanceDraft.urgency}
                  onChange={(event) =>
                    setMaintenanceDraft((current) => ({
                      ...current,
                      urgency: event.target.value
                    }))
                  }
                >
                  {urgencyOptions.map((urgency) => (
                    <option key={urgency} value={urgency}>
                      {urgency}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Reason</span>
              <textarea
                rows={3}
                value={maintenanceDraft.reason}
                onChange={(event) =>
                  setMaintenanceDraft((current) => ({
                    ...current,
                    reason: event.target.value
                  }))
                }
                placeholder="Describe why this maintenance task is needed"
              />
            </label>

            <button className="action-button" disabled={isCreatingMaintenance} type="submit">
              {isCreatingMaintenance ? "Creating..." : "Create maintenance task"}
            </button>
          </form>

          {!isLoading && maintenance.length === 0 ? (
            <div className="callout">No maintenance records matched the current filter set.</div>
          ) : (
            <div className="stack">
              {maintenance.map((record) => {
                const isBusy = busyMaintenanceId === record.id;

                return (
                  <article key={`${record.id}-${record.created_at}`} className="workflow-card">
                    <div className="workflow-card__header">
                      <div>
                        <span className="fleet-card__eyebrow">{record.elevator_id}</span>
                        <h4>{record.reason}</h4>
                      </div>
                      <span className={getMaintenanceTone(record)}>{record.status}</span>
                    </div>

                    <dl className="workflow-card__meta">
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

                    <div className="action-row">
                      {record.status !== "scheduled" ? (
                        <button
                          className="action-button action-button--secondary"
                          disabled={isBusy}
                          onClick={() => void handleMaintenanceStatus(record.id, "scheduled")}
                          type="button"
                        >
                          Schedule
                        </button>
                      ) : null}

                      {record.status !== "completed" ? (
                        <button
                          className="action-button"
                          disabled={isBusy}
                          onClick={() => void handleMaintenanceStatus(record.id, "completed")}
                          type="button"
                        >
                          Complete
                        </button>
                      ) : null}

                      {record.status !== "cancelled" ? (
                        <button
                          className="action-button action-button--ghost"
                          disabled={isBusy}
                          onClick={() => void handleMaintenanceStatus(record.id, "cancelled")}
                          type="button"
                        >
                          Cancel
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
