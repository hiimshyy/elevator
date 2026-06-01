import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { MetricSparkline } from "../components/charts/MetricSparkline";
import {
  ElevatorSummary,
  SensorReading,
  apiBaseUrl,
  listElevators,
  listReadings,
  wsBaseUrl
} from "../lib/api";
import { createSensorStreamUrl } from "../lib/ws";

const maxPoints = 60;

interface LivePoint {
  timestamp: string;
  accelRmsMg: number;
  velocityRmsMms: number;
  loadKg: number;
  temperatureC: number;
}

interface LiveStreamMessage {
  event: string;
  elevator_id: string;
  timestamp: string | null;
  readings: {
    accel_rms_mg: number | null;
    velocity_rms_mms: number | null;
    load_kg: number | null;
    vib_temperature_c: number | null;
    env_temperature_c: number | null;
  } | null;
  inference: {
    status: string | null;
    confidence: number | null;
    health_score: number | null;
  } | null;
  alert: boolean;
}

function normalizeReading(reading: SensorReading): LivePoint {
  return {
    timestamp: reading.timestamp,
    accelRmsMg: reading.accel_rms_mg ?? 0,
    velocityRmsMms: reading.velocity_rms_mms ?? 0,
    loadKg: reading.load_kg ?? 0,
    temperatureC: reading.vib_temperature_c ?? reading.env_temperature_c ?? 0
  };
}

function mergePoint(existing: LivePoint[], incoming: LivePoint): LivePoint[] {
  const next = [...existing];
  const index = next.findIndex((point) => point.timestamp === incoming.timestamp);

  if (index >= 0) {
    next[index] = incoming;
  } else {
    next.push(incoming);
  }

  next.sort((left, right) => left.timestamp.localeCompare(right.timestamp));
  return next.slice(-maxPoints);
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(new Date(value));
}

export function LiveMonitorPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [points, setPoints] = useState<LivePoint[]>([]);
  const [connectionState, setConnectionState] = useState("Connecting");
  const [error, setError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const selectedElevator = searchParams.get("elevator") ?? "elev-001";
  const readingsUrl = `${apiBaseUrl}/elevators/${selectedElevator}/readings?limit=${maxPoints}`;
  const socketUrl = createSensorStreamUrl(wsBaseUrl, selectedElevator);

  useEffect(() => {
    const controller = new AbortController();

    const loadElevators = async (): Promise<void> => {
      try {
        const nextElevators = await listElevators(controller.signal);
        setElevators(nextElevators);

        if (!searchParams.get("elevator") && nextElevators.length > 0) {
          setSearchParams({ elevator: nextElevators[0].id }, { replace: true });
        }
      } catch (nextError) {
        if (!controller.signal.aborted) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load elevators");
        }
      }
    };

    void loadElevators();

    return () => controller.abort();
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setHistoryLoaded(false);
    setPoints([]);
    setError(null);

    const loadHistory = async (): Promise<void> => {
      try {
        const readings = await listReadings(selectedElevator, maxPoints, controller.signal);
        const normalized = readings
          .map(normalizeReading)
          .sort((left, right) => left.timestamp.localeCompare(right.timestamp));
        setPoints(normalized);
      } catch (nextError) {
        if (!controller.signal.aborted) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load readings");
        }
      } finally {
        if (!controller.signal.aborted) {
          setHistoryLoaded(true);
        }
      }
    };

    void loadHistory();

    return () => controller.abort();
  }, [selectedElevator]);

  useEffect(() => {
    const socket = new WebSocket(socketUrl);
    setConnectionState("Connecting");

    socket.onopen = () => {
      setConnectionState("Live");
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as LiveStreamMessage;
      const timestamp = message.timestamp;
      const readings = message.readings;

      if (!readings || !timestamp) {
        return;
      }

      setPoints((current) =>
        mergePoint(current, {
          timestamp,
          accelRmsMg: readings.accel_rms_mg ?? 0,
          velocityRmsMms: readings.velocity_rms_mms ?? 0,
          loadKg: readings.load_kg ?? 0,
          temperatureC: readings.vib_temperature_c ?? readings.env_temperature_c ?? 0
        })
      );
    };

    socket.onerror = () => {
      setConnectionState("Socket error");
    };

    socket.onclose = () => {
      setConnectionState("Disconnected");
    };

    return () => {
      socket.close();
    };
  }, [socketUrl]);

  const latestPoint = points[points.length - 1] ?? null;
  const hasData = points.length > 0;

  const chartSeries = useMemo(
    () => ({
      accel: points.map((point) => point.accelRmsMg),
      velocity: points.map((point) => point.velocityRmsMms),
      load: points.map((point) => point.loadKg),
      temperature: points.map((point) => point.temperatureC)
    }),
    [points]
  );

  return (
    <section className="page">
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Live Monitor</h2>
        </div>
        <div className="status-pill">{connectionState}</div>
      </header>

      <div className="toolbar">
        <label className="field">
          <span>Select elevator</span>
          <select
            value={selectedElevator}
            onChange={(event) => setSearchParams({ elevator: event.target.value })}
          >
            {elevators.map((elevator) => (
              <option key={elevator.id} value={elevator.id}>
                {elevator.id}
              </option>
            ))}
          </select>
        </label>
        <div className="toolbar__meta">
          <span>History: {readingsUrl}</span>
          <span>Socket: {socketUrl}</span>
        </div>
      </div>

      {error ? <div className="callout callout--error">Live monitor error: {error}</div> : null}

      {!historyLoaded ? <div className="callout">Loading reading history...</div> : null}

      {historyLoaded && !hasData ? (
        <div className="callout">
          No readings available for <strong>{selectedElevator}</strong>.
        </div>
      ) : null}

      {latestPoint ? (
        <div className="metric-banner">
          <div>
            <span className="fleet-card__eyebrow">Latest sample</span>
            <strong>{formatTimestamp(latestPoint.timestamp)}</strong>
          </div>
          <div>
            <span className="fleet-card__eyebrow">Samples</span>
            <strong>{points.length}</strong>
          </div>
          <div>
            <span className="fleet-card__eyebrow">Selected elevator</span>
            <strong>{selectedElevator}</strong>
          </div>
        </div>
      ) : null}

      {hasData ? (
        <div className="chart-grid">
          <MetricSparkline
            color="#0f7c82"
            label="Accel RMS"
            points={chartSeries.accel}
            unit="mg"
          />
          <MetricSparkline
            color="#d07a14"
            label="Velocity RMS"
            points={chartSeries.velocity}
            unit="mm/s"
          />
          <MetricSparkline
            color="#196f47"
            label="Load"
            points={chartSeries.load}
            unit="kg"
          />
          <MetricSparkline
            color="#9c2f2f"
            label="Temperature"
            points={chartSeries.temperature}
            unit="C"
          />
        </div>
      ) : null}
    </section>
  );
}
