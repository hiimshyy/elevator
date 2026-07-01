// Feature: ui-ux-responsive-redesign
// Integration test for cross-route theme switching (task 20.2).
//
// Validates: Requirements 8.5
//
// Requirement 8.5 (paraphrased):
//   Selecting a theme SHALL apply the selected theme across the entire
//   Operations_Console within 500 milliseconds without requiring a full
//   page reload.
//
// What this test verifies:
//   1. The full app tree (ThemeProvider > LiveRegionProvider > Router > App)
//      renders and applies a theme.
//   2. Toggling the theme sets `data-theme` on `document.documentElement`
//      within 500ms.
//   3. Navigating to each of the four routes (/fleet, /live, /alerts,
//      /config) after a theme change shows the theme attribute persists —
//      the component tree stays mounted (no reload).
//   4. The theme can be toggled on any route and it immediately applies
//      everywhere.

import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveRegionProvider } from "../../a11y/LiveRegionProvider";
import { NavigationShell } from "../../components/layout/NavigationShell";
import { ThemeProvider, THEME_STORAGE_KEY } from "../ThemeProvider";

// ---------------------------------------------------------------------------
// Mock the data-fetching modules so pages render without network calls.
// We only need the shell and routing to stay mounted — actual page content
// is irrelevant for theme switching verification.
// ---------------------------------------------------------------------------

vi.mock("../../lib/api", () => ({
  listElevators: () => Promise.resolve([]),
  listReadings: () => Promise.resolve([]),
  listAlerts: () => Promise.resolve([]),
  listMaintenance: () => Promise.resolve([]),
  acknowledgeAlert: () => Promise.resolve({}),
  createMaintenance: () => Promise.resolve({}),
  updateMaintenance: () => Promise.resolve({}),
  apiUrl: (path: string) => `http://localhost:8000/api${path}`,
  getJson: () => Promise.resolve([]),
}));

vi.mock("../../lib/ws", () => ({
  createSensorStreamUrl: () => "ws://localhost:8000/ws/sensors/test",
  sensorStreamPath: () => "/ws/sensors/test",
}));

// ---------------------------------------------------------------------------
// Stub matchMedia — jsdom doesn't implement it. We stub it to return "light"
// as the OS preference so the initial theme resolves predictably.
// ---------------------------------------------------------------------------

function stubMatchMedia(): void {
  const matcher = (query: string): MediaQueryList => ({
    matches: query.includes("prefers-color-scheme: light"),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  } as unknown as MediaQueryList);

  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: matcher,
  });
}

// ---------------------------------------------------------------------------
// Minimal page stubs — we render lightweight placeholders for each route
// so the test focuses on the theme mechanism, not page content.
// ---------------------------------------------------------------------------

function FleetStub(): JSX.Element {
  return <div data-testid="page-fleet">Fleet Overview</div>;
}
function LiveStub(): JSX.Element {
  return <div data-testid="page-live">Live Monitor</div>;
}
function AlertsStub(): JSX.Element {
  return <div data-testid="page-alerts">Alerts & Maintenance</div>;
}
function ConfigStub(): JSX.Element {
  return <div data-testid="page-config">Local Config</div>;
}

// ---------------------------------------------------------------------------
// Test app renderer — mirrors the real provider hierarchy from main.tsx.
// ---------------------------------------------------------------------------

function renderApp(initialRoute = "/fleet") {
  return render(
    <ThemeProvider>
      <LiveRegionProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route element={<NavigationShell />}>
              <Route path="/fleet" element={<FleetStub />} />
              <Route path="/live" element={<LiveStub />} />
              <Route path="/alerts" element={<AlertsStub />} />
              <Route path="/config" element={<ConfigStub />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </LiveRegionProvider>
    </ThemeProvider>,
  );
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("Cross-route theme switching (Requirement 8.5)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    stubMatchMedia();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("applies theme to document.documentElement immediately on toggle", async () => {
    renderApp("/fleet");

    // Initial state: light theme applied.
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Toggle to dark.
    const toggle = screen.getByTestId("theme-toggle");
    await act(async () => {
      toggle.click();
    });

    // Theme must be applied — check within 500ms budget.
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("applies theme within 500ms without a full page reload", async () => {
    renderApp("/fleet");

    // Mark the component tree as mounted by checking for a sentinel element.
    const mainContent = screen.getByRole("main");
    expect(mainContent).toBeInTheDocument();

    const startTime = performance.now();

    // Toggle theme.
    const toggle = screen.getByTestId("theme-toggle");
    await act(async () => {
      toggle.click();
    });

    const elapsed = performance.now() - startTime;

    // Theme applied within 500ms budget (Requirement 8.5).
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(elapsed).toBeLessThan(500);

    // The main content area is still rendered — proves no full reload occurred.
    // A reload would unmount the entire React tree.
    expect(screen.getByRole("main")).toBe(mainContent);
  });

  it("persists theme across navigation to all four routes without reload", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp("/fleet");

    // Verify initial route.
    expect(screen.getByTestId("page-fleet")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Toggle to dark on the fleet route.
    const toggle = screen.getByTestId("theme-toggle");
    await act(async () => {
      toggle.click();
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Navigate to /live via the nav link.
    const liveLink = screen.getByRole("link", { name: "Live Monitor" });
    await user.click(liveLink);
    expect(screen.getByTestId("page-live")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Navigate to /alerts.
    const alertsLink = screen.getByRole("link", { name: "Alerts & Maintenance" });
    await user.click(alertsLink);
    expect(screen.getByTestId("page-alerts")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Navigate to /config.
    const configLink = screen.getByRole("link", { name: "Local Config" });
    await user.click(configLink);
    expect(screen.getByTestId("page-config")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Navigate back to /fleet — theme still applied.
    const fleetLink = screen.getByRole("link", { name: "Fleet Overview" });
    await user.click(fleetLink);
    expect(screen.getByTestId("page-fleet")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("allows theme toggling on any route and applies everywhere", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp("/fleet");

    // Navigate to /config first.
    const configLink = screen.getByRole("link", { name: "Local Config" });
    await user.click(configLink);
    expect(screen.getByTestId("page-config")).toBeInTheDocument();

    // Toggle to dark on /config.
    const toggle = screen.getByTestId("theme-toggle");
    await act(async () => {
      toggle.click();
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Navigate to /fleet — dark theme persists.
    const fleetLink = screen.getByRole("link", { name: "Fleet Overview" });
    await user.click(fleetLink);
    expect(screen.getByTestId("page-fleet")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Toggle back to light on /fleet.
    await act(async () => {
      toggle.click();
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Navigate to /live — light theme persists.
    const liveLink = screen.getByRole("link", { name: "Live Monitor" });
    await user.click(liveLink);
    expect(screen.getByTestId("page-live")).toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("persists selected theme to localStorage so it survives session within budget", async () => {
    renderApp("/fleet");

    // Toggle to dark.
    const toggle = screen.getByTestId("theme-toggle");
    await act(async () => {
      toggle.click();
    });

    // localStorage receives the preference (Requirement 8.6).
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    // data-theme is set on documentElement.
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
