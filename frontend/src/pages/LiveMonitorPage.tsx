import { startTransition, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { MetricSparkline } from "../components/charts/MetricSparkline";
import { PageContainer, ResponsiveGrid } from "../components/layout/PageContainer";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { Select } from "../components/ui/Field";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  mapConnectionStateToState,
  type ConnectionState,
} from "../components/ui/statusState";
import {
  ElevatorSummary,
  SensorReading,
  listElevators,
  listReadings,
} from "../lib/api";
import { useLocalConfig } from "../lib/localConfig";
import { createSensorStreamUrl } from "../lib/ws";

// =============================================================================
// Live Monitor route — refactored to consume the redesigned UI primitives.
//
// Requirements covered:
//   - 4.5 : metric charts arranged in a single column at Mobile — the
//           ResponsiveGrid inherits `columnCount` from useBreakpoint(),
//           which yields 1 at Mobile (and up to 2 elsewhere here).
//   - 6.9 : accessible text alternative for each MetricSparkline (owned
//           by MetricSparkline itself once the timestamp / value / unit
//           props are supplied).
//   - 7.6 : persistent synthetic-trace label — the page renders a
//           persistent banner whenever ANY point in the display series
//           is synthetic, and each MetricSparkline receives
//           `hasSyntheticPoints` so it renders its own per-chart marker.
//   - 7.7 : WebSocket connection state normalized to exactly three
//           mutually distinct treatments (connected / connecting /
//           disconnected) driven by the status-state mapper and rendered
//           through StatusBadge. React batches the setState -> re-render
//           on every socket event, so the badge updates well within 1s.
//   - 7.8 : the legacy toolbar meta rows that surfaced the REST readings
//           URL and the WebSocket URL are removed; endpoint URLs are
//           confined to the Local Config route.
// =============================================================================

const MAX_POINTS = 60;

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
    source: "actual",
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
  return next.slice(-MAX_POINTS);
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
    temperatureC: (latest.temperatureC - previousPoint.temperatureC) * trendWeight,
  };

  const amplitude = {
    accelRmsMg: Math.max(0.8, latest.accelRmsMg * 0.018),
    velocityRmsMms: Math.max(0.05, latest.velocityRmsMms * 0.03),
    loadKg: Math.max(1.2, latest.loadKg * 0.006),
    temperatureC: Math.max(0.08, latest.temperatureC * 0.01),
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
    source: "synthetic",
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

  return [...actualPoints, ...syntheticPoints].slice(-MAX_POINTS);
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function formatControllerValue(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "N/A";
  }
  return value.toLocaleString();
}

/**
 * Descriptive label for each canonical connection state. Kept alongside
 * the state so both the badge (via labelOverride) and the announcer
 * message read the same wording.
 */
const CONNECTION_STATE_LABEL: Record<ConnectionState, string> = {
  connected: "Live socket connected",
  connecting: "Socket connecting",
  disconnected: "Socket disconnected",
};

const VIEW_LABEL = "Live Monitor";

export function LiveMonitorPage(): JSX.Element {
  const { apiBaseUrl, apiKey, wsBaseUrl } = useLocalConfig();
  const [searchParams, setSearchParams] = useSearchParams();
  const [elevators, setElevators] = useState<ElevatorSummary[]>([]);
  const [points, setPoints] = useState<LivePoint[]>([]);
  // Canonical three-state connection status (Req 7.7). The socket
  // lifecycle collapses to exactly these three values so the StatusBadge
  // renders one of exactly three mutually-distinct treatments.
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const selectedElevator = searchParams.get("elevator") ?? "elev-001";
  // Socket URL and REST readings path are still computed for the fetcher
  // / WebSocket, but they are no longer displayed anywhere on this page
  // (Requirement 7.8).
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
        const readings = await listReadings(selectedElevator, MAX_POINTS, controller.signal);
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
    // Requirement 7.7: normalize the pre-open state to "connecting" so
    // the badge starts in the canonical three-state set.
    setConnectionState("connecting");

    socket.onopen = () => {
      setConnectionState("connected");
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
          source: "actual",
        })
      );
      setNowMs(Date.now());
    };

    socket.onerror = () => {
      // Both error and close land in "disconnected" — from the operator's
      // perspective these are the same "we're not receiving data" state.
      setConnectionState("disconnected");
    };

    socket.onclose = () => {
      setConnectionState("disconnected");
    };

    return () => {
      socket.close();
    };
  }, [socketUrl]);

  const displayPoints = useMemo(() => buildDisplayPoints(points, nowMs), [nowMs, points]);
  const latestActualPoint = points[points.length - 1] ?? null;
  const latestDisplayPoint = displayPoints[displayPoints.length - 1] ?? null;
  const hasData = displayPoints.length > 0;
  const hasSyntheticPoints = useMemo(
    () => displayPoints.some((point) => point.source === "synthetic"),
    [displayPoints]
  );
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
      temperature: displayPoints.map((point) => point.temperatureC),
    }),
    [displayPoints]
  );

  const connectionBadgeState = mapConnectionStateToState(connectionState);
  const connectionBadgeLabel = CONNECTION_STATE_LABEL[connectionState];

  return (
    <PageContainer>
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Live Monitor</h2>
        </div>
        {/* Requirement 7.7: exactly three mutually-distinct treatments.
            StatusBadge combines color + icon + label + shape, and the
            connection-state -> status-state mapping is total across the
            three canonical states so this badge is always exactly one of
            three visually-distinct renderings. */}
        <StatusBadge
          state={connectionBadgeState}
          labelOverride={connectionBadgeLabel}
          data-connection-state={connectionState}
          data-testid="live-monitor-connection-badge"
        />
      </header>

      {/* Elevator selector — uses the Field/Select primitive which
          guarantees label association, 44px touch target, and validation
          wiring. The primitive is required by the redesign in place of
          the legacy .toolbar / .field literal markup. The endpoint URL
          rows that previously accompanied the selector have been removed
          (Requirement 7.8). */}
      <ResponsiveGrid maxColumns={2}>
        <Card elevation="flat">
          <Select
            label="Select elevator"
            value={selectedElevator}
            onChange={(event) => setSearchParams({ elevator: event.target.value })}
            options={elevators.map((elevator) => ({
              value: elevator.id,
              label: elevator.id,
            }))}
          />
        </Card>
        <Card title="Signal source" headingLevel={3} elevation="flat">
          <p>
            {latestDisplayPoint?.source === "synthetic"
              ? "Currently rendering an interpolated live trace."
              : "Currently rendering the latest live packet."}
          </p>
        </Card>
      </ResponsiveGrid>

      {error ? (
        <DataState
          state="error"
          viewLabel={VIEW_LABEL}
          errorReason={error}
        />
      ) : null}

      {!historyLoaded ? (
        <DataState state="loading" viewLabel={VIEW_LABEL} />
      ) : null}

      {historyLoaded && !hasData ? (
        <DataState
          state="empty"
          viewLabel={VIEW_LABEL}
          missingDataLabel={`readings for ${selectedElevator}`}
        />
      ) : null}

      {latestActualPoint ? (
        <>
          {/* Requirement 7.6: persistent page-level label whenever the
              display series contains any interpolated (synthetic) point.
              Rendered as its own Card so it stays visible independent of
              scroll position within the metric-banner cluster. */}
          {hasSyntheticPoints ? (
            <Card
              elevation="flat"
              className="live-monitor__synthetic-banner"
              data-testid="live-monitor-synthetic-banner"
            >
              <p>
                <strong>Synthetic interpolated trace visible.</strong> Charts
                include one or more interpolated points generated between live
                packets so the trend stays continuous. Interpolated segments are
                labeled per chart.
              </p>
            </Card>
          ) : null}

          <ResponsiveGrid maxColumns={3} aria-label="Live packet metrics">
            <Card title="Latest packet" headingLevel={3} elevation="flat">
              <p>{formatTimestamp(latestActualPoint.timestamp)}</p>
            </Card>
            <Card title="Realtime phase" headingLevel={3} elevation="flat">
              <p>{streamPhase}</p>
            </Card>
            <Card title="Packet age" headingLevel={3} elevation="flat">
              <p>{secondsSinceActualSample ?? 0}s ago</p>
            </Card>
            <Card title="Rendered samples" headingLevel={3} elevation="flat">
              <p>{displayPoints.length}</p>
            </Card>
            <Card title="Signal source" headingLevel={3} elevation="flat">
              <p>
                {latestDisplayPoint?.source === "synthetic"
                  ? "Interpolated live trace"
                  : "Live packet"}
              </p>
            </Card>
            <Card title="Selected elevator" headingLevel={3} elevation="flat">
              <p>{selectedElevator}</p>
            </Card>
          </ResponsiveGrid>

          <ResponsiveGrid maxColumns={3} aria-label="RS-485 controller registers">
            <Card title="Controller (RS-485)" headingLevel={3} elevation="flat">
              <p>{hasControllerData ? "Connected" : "No controller data"}</p>
            </Card>
            <Card title="Register 1047" headingLevel={3} elevation="flat">
              <p>{formatControllerValue(latestActualPoint.controllerRegister1047)}</p>
            </Card>
            <Card title="Register 0x2121" headingLevel={3} elevation="flat">
              <p>{formatControllerValue(latestActualPoint.controllerRegister0x2121)}</p>
            </Card>
            <Card title="Register 0x2122" headingLevel={3} elevation="flat">
              <p>{formatControllerValue(latestActualPoint.controllerRegister0x2122)}</p>
            </Card>
            <Card title="Controller timestamp" headingLevel={3} elevation="flat">
              <p>{formatTimestamp(latestActualPoint.timestamp)}</p>
            </Card>
            <Card title="Field note" headingLevel={3} elevation="flat">
              <p>
                {hasControllerData
                  ? "Live controller values"
                  : "Waiting for controller packet"}
              </p>
            </Card>
          </ResponsiveGrid>

          <Card elevation="flat">
            <p>
              Controller values above come from the RS-485 elevator controller.
              The vibration, temperature, and load charts remain mock-generated
              while the external sensors are not installed.
            </p>
          </Card>
        </>
      ) : null}

      {hasData ? (
        // Requirement 4.5: single-column at Mobile. ResponsiveGrid
        // inherits the breakpoint's `columnCount` (1 on Mobile) and is
        // capped at 2 so Tablet+ gets at most a 2-up chart layout.
        <ResponsiveGrid maxColumns={2} aria-label="Live metric charts">
          <MetricSparkline
            color="#0f7c82"
            label="Accel RMS"
            points={chartSeries.accel}
            unit="mg"
            latestTimestamp={latestDisplayPoint?.timestamp ?? null}
            hasSyntheticPoints={hasSyntheticPoints}
          />
          <MetricSparkline
            color="#d07a14"
            label="Velocity RMS"
            points={chartSeries.velocity}
            unit="mm/s"
            latestTimestamp={latestDisplayPoint?.timestamp ?? null}
            hasSyntheticPoints={hasSyntheticPoints}
          />
          <MetricSparkline
            color="#196f47"
            label="Load"
            points={chartSeries.load}
            unit="kg"
            latestTimestamp={latestDisplayPoint?.timestamp ?? null}
            hasSyntheticPoints={hasSyntheticPoints}
          />
          <MetricSparkline
            color="#9c2f2f"
            label="Temperature"
            points={chartSeries.temperature}
            unit="C"
            latestTimestamp={latestDisplayPoint?.timestamp ?? null}
            hasSyntheticPoints={hasSyntheticPoints}
          />
        </ResponsiveGrid>
      ) : null}
    </PageContainer>
  );
}
