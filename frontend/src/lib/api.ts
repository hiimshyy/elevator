import { getLocalConfig } from "./localConfig";

export function apiUrl(path: string): string {
  const { apiBaseUrl } = getLocalConfig();
  return `${apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

export interface ElevatorSummary {
  id: string;
  max_capacity_kg: number;
  created_at: string;
  latest_health_score: number | null;
  status: string | null;
}

export interface SensorReading {
  id: number | null;
  elevator_id: string;
  timestamp: string;
  accel_rms_mg: number | null;
  velocity_rms_mms: number | null;
  peak_accel_mg: number | null;
  vib_temperature_c: number | null;
  env_temperature_c: number | null;
  env_humidity_pct: number | null;
  load_kg: number | null;
  controller_register_1047: number | null;
  controller_register_0x2121: number | null;
  controller_register_0x2122: number | null;
  synced: number;
}

export interface AlertRecord {
  id: number | null;
  elevator_id: string;
  timestamp: string;
  severity: string;
  message: string;
  acknowledged: number;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export interface MaintenanceRecord {
  id: number | null;
  elevator_id: string;
  recommended_date: string;
  urgency: string;
  reason: string;
  estimated_rul_hours: number | null;
  status: string;
  completed_at: string | null;
  technician: string | null;
  created_at: string;
}

export interface CreateMaintenancePayload {
  elevator_id: string;
  recommended_date: string;
  urgency: string;
  reason: string;
}

export interface UpdateMaintenancePayload {
  status?: string;
  completedAt?: string;
  technician?: string;
}

interface RequestOptions {
  body?: BodyInit | null;
  headers?: HeadersInit;
  method?: string;
  signal?: AbortSignal;
}

function toQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { apiKey } = getLocalConfig();

  const response = await fetch(apiUrl(path), {
    method: options.method ?? "GET",
    headers: {
      "X-API-Key": apiKey,
      ...options.headers
    },
    body: options.body,
    signal: options.signal
  });

  if (!response.ok) {
    let detail = `API request failed with HTTP ${response.status}`;

    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) {
        detail = data.detail;
      }
    } catch {
      // Ignore non-JSON error bodies and use the HTTP status fallback above.
    }

    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { signal });
}

export interface CreateElevatorPayload {
  id: string;
  name: string;
  location: string;
  max_capacity_kg: number;
  install_date: string;
}

export function deleteElevator(elevatorId: string): Promise<void> {
  return requestJson<void>(`/elevators/${elevatorId}`, {
    method: "DELETE",
  });
}

export function createElevator(payload: CreateElevatorPayload): Promise<ElevatorSummary> {
  return requestJson<ElevatorSummary>("/elevators/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listElevators(signal?: AbortSignal): Promise<ElevatorSummary[]> {
  return getJson<ElevatorSummary[]>("/elevators", signal);
}

export function listReadings(
  elevatorId: string,
  limit = 60,
  signal?: AbortSignal
): Promise<SensorReading[]> {
  return getJson<SensorReading[]>(`/elevators/${elevatorId}/readings?limit=${limit}`, signal);
}

export function listAlerts(
  filters: {
    elevatorId?: string;
    severity?: string;
    acknowledged?: boolean;
  } = {},
  signal?: AbortSignal
): Promise<AlertRecord[]> {
  const query = toQueryString({
    elevator_id: filters.elevatorId,
    severity: filters.severity,
    acknowledged: filters.acknowledged
  });

  return getJson<AlertRecord[]>(`/alerts${query}`, signal);
}

export function acknowledgeAlert(alertId: number, technician: string): Promise<AlertRecord> {
  return requestJson<AlertRecord>(`/alerts/${alertId}/acknowledge`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ technician })
  });
}

export function listMaintenance(
  filters: {
    elevatorId?: string;
    status?: string;
  } = {},
  signal?: AbortSignal
): Promise<MaintenanceRecord[]> {
  const query = toQueryString({
    elevator_id: filters.elevatorId,
    status: filters.status
  });

  return getJson<MaintenanceRecord[]>(`/maintenance${query}`, signal);
}

export function createMaintenance(
  payload: CreateMaintenancePayload
): Promise<MaintenanceRecord> {
  return requestJson<MaintenanceRecord>("/maintenance", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export function updateMaintenance(
  maintenanceId: number,
  payload: UpdateMaintenancePayload
): Promise<MaintenanceRecord> {
  const query = toQueryString({
    status: payload.status,
    completed_at: payload.completedAt,
    technician: payload.technician
  });

  return requestJson<MaintenanceRecord>(`/maintenance/${maintenanceId}${query}`, {
    method: "PATCH"
  });
}
