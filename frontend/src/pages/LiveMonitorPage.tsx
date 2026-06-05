import { startTransition, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { MetricSparkline } from "../components/charts/MetricSparkline";
import {
  ElevatorSummary,
  SensorReading,
  listElevators,
  listReadings,
} from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";
import { createSensorStreamUrl } from "../lib/ws";

const maxPoints = 60;

interface LivePoint {
  timestamp: string;
  accelRmsMg: number;
  velocityRmsMms: number;
  loadKg: number;
  temperatureC: number;
  controllerRegister1047: number | null;
  controllerRegister0x2121: number | null;
  controllerRegister0x2122: number | null;
  source: "actual" | "synthetic";
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
    controller_register_1047: number | null;
    controller_register_0x2121: number | null;
    controller_register_0x2122: number | null;
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
    temperatureC: reading.vib_temperature_c ?? reading.env_temperature_c ?? 0,
    controllerRegister1047: reading.controller_register_1047 ?? null,
    controllerRegister0x2121: reading.controller_register_0x2121 ?? null,
    controllerRegister0x2122: reading.controller_register_0x2122 ?? null,
    source: "actual"
  };
}

function mergePoint(existing: LivePoint[], incoming: LivePoint): LivePoint[] {
  const next = existing.filter((point) => point.source === "actual");
  const index = next.findIndex((point) => point.timestamp === incoming.timestamp);

  if (index >= 0) {
    next[index] = incoming;
  } else {
    next.push(incoming);
  }

  next.sort((left, right) => left.timestamp.localeCompare(right.timestamp));
  return next.slice(-maxPoints);
}

function clampMetric(value: number): number {
  return Number.isFinite(value) ? Math.max(0, value) : 0;
}

function createSyntheticPoint(
  latest: LivePoint,
  previous: LivePoint | null,
  elapsedMs: number,
  sequence: number
): LivePoint {
  const trendWeight = 0.18;
  const previousPoint = previous ?? latest;
  const oscillation = elapsedMs / 1000 + sequence;
  const jitter = Math.sin(oscillation * 1.4);
  const secondaryJitter = Math.cos(oscillation * 1.1);

  const trend = {
    accelRmsMg: (latest.accelRmsMg - previousPoint.accelRmsMg) * trendWeight,
    velocityRmsMms: (latest.velocityRmsMms - previousPoint.velocityRmsMms) * trendWeight,
    loadKg: (latest.loadKg - previousPoint.loadKg) * trendWeight,
    temperatureC: (latest.temperatureC - previousPoint.temperatureC) * trendWeight
  };

  const amplitude = {
    accelRmsMg: Math.max(0.8, latest.accelRmsMg * 0.018),
    velocityRmsMms: Math.max(0.05, latest.velocityRmsMms * 0.03),
    loadKg: Math.max(1.2, latest.loadKg * 0.006),
    temperatureC: Math.max(0.08, latest.temperatureC * 0.01)
  };

  return {
    timestamp: new Date(Date.now() + sequence * 1000).toISOString(),
    accelRmsMg: clampMetric(latest.accelRmsMg + trend.accelRmsMg + jitter * amplitude.accelRmsMg),
    velocityRmsMms: clampMetric(
      latest.velocityRmsMms + trend.velocityRmsMms + secondaryJitter * amplitude.velocityRmsMms
    ),
    loadKg: clampMetric(latest.loadKg + trend.loadKg + jitter * amplitude.loadKg * 0.7),
    temperatureC: clampMetric(
      latest.temperatureC + trend.temperatureC + secondaryJitter * amplitude.temperatureC
    ),
    controllerRegister1047: latest.controllerRegister1047,
    controllerRegister0x2121: latest.controllerRegister0x2121,
    controllerRegister0x2122: latest.controllerRegister0x2122,
    source: "synthetic"
  };
}

function buildDisplayPoints(actualPoints: LivePoint[], nowMs: number): LivePoint[] {
  if (actualPoints.length === 0) {
    return [];
  }

  const latest = actualPoints[actualPoints.length - 1];
  const previous = actualPoints.length > 1 ? actualPoints[actualPoints.length - 2] : null;
  const latestMs = new Date(latest.timestamp).getTime();
  if (Number.isNaN(latestMs)) {
    return actualPoints;
  }

  const elapsedMs = Math.max(0, nowMs - latestMs);
  const syntheticCount = Math.min(4, Math.floor(elapsedMs / 1000));

  if (syntheticCount === 0) {
    return actualPoints;
  }

  const syntheticPoints = Array.from({ length: syntheticCount }, (_, index) =>
    createSyntheticPoint(latest, previous, elapsedMs, index + 1)
  );

  return [...actualPoints, ...syntheticPoints].slice(-maxPoints);
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(date);
}

function formatControllerValue(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "N/A";
  }

  return value.toLocaleString();
}

export function LiveMonitorPage(): JSX.Element {
  const { apiBaseUrl, apiKey, wsBaseUrl } = useLocalConfig();
  const [searchParams, setSearchParams] = useSearchParams();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [points, setPoints] = useState<LivePoint[]>([]);
  const [connectionState, setConnectionState] = useState("Connecting");
  const [error, setError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

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
  }, [apiBaseUrl, apiKey, searchParams, setSearchParams]);

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
  }, [apiBaseUrl, apiKey, selectedElevator]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      startTransition(() => {
        setNowMs(Date.now());
      });
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, []);

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
          temperatureC: readings.vib_temperature_c ?? readings.env_temperature_c ?? 0,
          controllerRegister1047: readings.controller_register_1047 ?? null,
          controllerRegister0x2121: readings.controller_register_0x2121 ?? null,
          controllerRegister0x2122: readings.controller_register_0x2122 ?? null,
          source: "actual"
        })
      );
      setNowMs(Date.now());
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

  const displayPoints = useMemo(() => buildDisplayPoints(points, nowMs), [nowMs, points]);
  const latestActualPoint = points[points.length - 1] ?? null;
  const latestDisplayPoint = displayPoints[displayPoints.length - 1] ?? null;
  const hasData = displayPoints.length > 0;
  const hasControllerData = Boolean(
    latestActualPoint &&
      (latestActualPoint.controllerRegister1047 !== null ||
        latestActualPoint.controllerRegister0x2121 !== null ||
        latestActualPoint.controllerRegister0x2122 !== null)
  );
  const secondsSinceActualSample = latestActualPoint
    ? Math.max(0, Math.floor((nowMs - new Date(latestActualPoint.timestamp).getTime()) / 1000))
    : null;
  const streamPhase =
    secondsSinceActualSample === null
      ? "Awaiting first packet"
      : secondsSinceActualSample < 5
        ? "Collecting"
        : "Holding last packet";

  const chartSeries = useMemo(
    () => ({
      accel: displayPoints.map((point) => point.accelRmsMg),
      velocity: displayPoints.map((point) => point.velocityRmsMms),
      load: displayPoints.map((point) => point.loadKg),
      temperature: displayPoints.map((point) => point.temperatureC)
    }),
    [displayPoints]
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

      {latestActualPoint ? (
        <>
          <div className="metric-banner metric-banner--live">
            <div>
              <span className="fleet-card__eyebrow">Latest packet</span>
              <strong>{formatTimestamp(latestActualPoint.timestamp)}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Realtime phase</span>
              <strong>{streamPhase}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Packet age</span>
              <strong>{secondsSinceActualSample ?? 0}s ago</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Rendered samples</span>
              <strong>{displayPoints.length}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Signal source</span>
              <strong>
                {latestDisplayPoint?.source === "synthetic" ? "Interpolated live trace" : "Live packet"}
              </strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Selected elevator</span>
              <strong>{selectedElevator}</strong>
            </div>
          </div>

          <div className="metric-banner">
            <div>
              <span className="fleet-card__eyebrow">Controller (RS-485)</span>
              <strong>{hasControllerData ? "Connected" : "No controller data"}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Register 1047</span>
              <strong>{formatControllerValue(latestActualPoint.controllerRegister1047)}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Register 0x2121</span>
              <strong>{formatControllerValue(latestActualPoint.controllerRegister0x2121)}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Register 0x2122</span>
              <strong>{formatControllerValue(latestActualPoint.controllerRegister0x2122)}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Controller timestamp</span>
              <strong>{formatTimestamp(latestActualPoint.timestamp)}</strong>
            </div>
            <div>
              <span className="fleet-card__eyebrow">Field note</span>
              <strong>
                {hasControllerData ? "Live controller values" : "Waiting for controller packet"}
              </strong>
            </div>
          </div>

          <div className="callout">
            Controller values above come from the RS-485 elevator controller. The vibration,
            temperature, and load charts remain mock-generated while the external sensors are not
            installed.
          </div>
        </>
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
