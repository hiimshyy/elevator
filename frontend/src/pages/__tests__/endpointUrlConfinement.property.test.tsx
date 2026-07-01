// Feature: ui-ux-responsive-redesign, Property 14: Endpoint URLs are confined to the Local Config route
//
// Validates: Requirements 7.8
//
// Property 14 (from design.md):
//   For all renders of any non-Config route with arbitrary data, the rendered
//   output contains no internal endpoint URL (REST base URL or WebSocket URL).
//
// Requirement 7.8 (from requirements.md):
//   THE Operations_Console SHALL present internal endpoint URLs only within the
//   Local Config route and SHALL NOT present internal endpoint URLs in any other
//   route.
//
// Test strategy
// -------------
// We enumerate the three non-Config routes (Fleet Overview, Live Monitor,
// Alerts & Maintenance) via `fc.constantFrom`. For each route, we render the
// corresponding page component with mocked dependencies (api, ws, localConfig)
// so no real network calls occur, and assert that the rendered `textContent`
// does NOT contain either the REST API base URL or the WebSocket base URL.
//
// As a complementary assertion, we verify the Config route DOES contain the
// endpoint URLs, confirming they are confined there.

import { cleanup, render } from "@testing-library/react";
import * as fc from "fast-check";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveRegionProvider } from "../../a11y";
import { ThemeProvider } from "../../theme/ThemeProvider";

// ─── Known endpoint URLs that localConfig will return ────────────────────────
const MOCK_API_BASE_URL = "http://localhost:8000/api";
const MOCK_WS_BASE_URL = "ws://localhost:8000";
const MOCK_API_KEY = "test-key-123";

// ─── Mock localConfig ────────────────────────────────────────────────────────
vi.mock("../../lib/localConfig", () => ({
  useLocalConfig: () => ({
    apiBaseUrl: MOCK_API_BASE_URL,
    wsBaseUrl: MOCK_WS_BASE_URL,
    apiKey: MOCK_API_KEY,
    isUsingDefaults: true,
  }),
  getLocalConfig: () => ({
    apiBaseUrl: MOCK_API_BASE_URL,
    wsBaseUrl: MOCK_WS_BASE_URL,
    apiKey: MOCK_API_KEY,
    isUsingDefaults: true,
  }),
  getDefaultLocalConfig: () => ({
    apiBaseUrl: MOCK_API_BASE_URL,
    apiKey: MOCK_API_KEY,
  }),
  saveLocalConfig: vi.fn(),
  resetLocalConfig: vi.fn(),
  buildWsBaseUrl: (apiBaseUrl: string) =>
    apiBaseUrl.replace(/^http/, "ws").replace(/\/api$/, ""),
}));

// ─── Mock api module ─────────────────────────────────────────────────────────
vi.mock("../../lib/api", () => ({
  listElevators: vi.fn().mockResolvedValue([]),
  listReadings: vi.fn().mockResolvedValue([]),
  listAlerts: vi.fn().mockResolvedValue([]),
  listMaintenance: vi.fn().mockResolvedValue([]),
  acknowledgeAlert: vi.fn().mockResolvedValue({}),
  createMaintenance: vi.fn().mockResolvedValue({}),
  updateMaintenance: vi.fn().mockResolvedValue({}),
  apiUrl: (path: string) => `${MOCK_API_BASE_URL}${path}`,
  getJson: vi.fn().mockResolvedValue([]),
}));

// ─── Mock ws module ──────────────────────────────────────────────────────────
vi.mock("../../lib/ws", () => ({
  sensorStreamPath: (elevatorId: string) => `/ws/sensors/${elevatorId}`,
  createSensorStreamUrl: (baseUrl: string, elevatorId: string) =>
    `${baseUrl}/ws/sensors/${elevatorId}`,
}));

// ─── Mock WebSocket global ───────────────────────────────────────────────────
class MockWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: unknown) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor() {
    // Simulate connecting state; never fire onopen to keep it simple
  }
}
vi.stubGlobal("WebSocket", MockWebSocket);

// ─── Mock useViewState to avoid real fetch calls ─────────────────────────────
vi.mock("../../lib/viewState", () => ({
  useViewState: () => ({
    state: "empty",
    data: null,
    error: null,
    lastUpdatedAt: null,
    showLoadingIndicator: false,
    retry: vi.fn(),
  }),
  initialViewState: () => ({
    state: "loading",
    data: null,
    error: null,
    lastUpdatedAt: null,
  }),
}));

// ─── Import page components after mocks are set up ───────────────────────────
import { AlertsMaintenancePage } from "../AlertsMaintenancePage";
import { ConfigPage } from "../ConfigPage";
import { FleetOverviewPage } from "../FleetOverviewPage";
import { LiveMonitorPage } from "../LiveMonitorPage";

afterEach(() => {
  cleanup();
});

// ─── Route-to-component mapping ─────────────────────────────────────────────
type NonConfigRoute = "fleet" | "live" | "alerts";

const routeComponents: Record<NonConfigRoute, () => JSX.Element> = {
  fleet: FleetOverviewPage,
  live: LiveMonitorPage,
  alerts: AlertsMaintenancePage,
};

const routePaths: Record<NonConfigRoute, string> = {
  fleet: "/fleet",
  live: "/live",
  alerts: "/alerts",
};

/**
 * Helper that renders a page component inside all required providers.
 */
function renderRoute(route: NonConfigRoute) {
  const Component = routeComponents[route];
  const path = routePaths[route];

  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <LiveRegionProvider>
          <Component />
        </LiveRegionProvider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe("Property 14: Endpoint URLs are confined to the Local Config route", () => {
  /**
   * Property 14a — Non-Config routes do not render endpoint URLs
   * Validates: Requirements 7.8
   *
   * For every non-Config route, the rendered text content does not contain
   * the REST API base URL or the WebSocket base URL.
   */
  it("14a: non-Config routes do not contain internal endpoint URLs", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<NonConfigRoute>("fleet", "live", "alerts"),
        (route) => {
          cleanup();
          const { container } = renderRoute(route);
          const textContent = container.textContent ?? "";

          // The REST base URL must not appear anywhere in the rendered text
          expect(textContent).not.toContain(MOCK_API_BASE_URL);
          // The WebSocket base URL must not appear anywhere in the rendered text
          expect(textContent).not.toContain(MOCK_WS_BASE_URL);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Complementary assertion — Config route DOES contain endpoint URLs.
   * This confirms the confinement: the URLs exist somewhere, just not
   * on the non-Config routes.
   */
  it("14b: Config route presents internal endpoint URLs", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/config"]}>
        <ThemeProvider>
          <LiveRegionProvider>
            <ConfigPage />
          </LiveRegionProvider>
        </ThemeProvider>
      </MemoryRouter>
    );

    const textContent = container.textContent ?? "";

    // The Config page displays API base URL in the "Current API" card and
    // within the form fields/preview text
    expect(textContent).toContain(MOCK_API_BASE_URL);
    // The Config page also displays the WebSocket base URL in the
    // "Current socket" card
    expect(textContent).toContain(MOCK_WS_BASE_URL);
  });
});
