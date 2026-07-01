// Feature: ui-ux-responsive-redesign
// Smoke test for NavigationShell component and reducer (task 12.1).
//
// Validates basic rendering and the exported `navReducer` contract. The
// dedicated property test for the toggle reducer is task 12.2; the property
// test for the active-link non-color distinction is task 12.3. This file
// only verifies the component mounts, exposes the structural elements
// required by the design (skip link, brand, nav links, theme toggle,
// outlet), and that the reducer responds correctly to its actions.

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ThemeProvider } from "../../../theme";
import {
  NavigationShell,
  initialNavState,
  navReducer,
  NAV_ITEMS,
} from "../NavigationShell";

function renderShellAt(path: string): void {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<NavigationShell />}>
            <Route path="/fleet" element={<p>Fleet content</p>} />
            <Route path="/live" element={<p>Live content</p>} />
            <Route path="/alerts" element={<p>Alerts content</p>} />
            <Route path="/config" element={<p>Config content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("NavigationShell — smoke", () => {
  it("renders the skip link, brand, every nav link, the theme toggle, and the outlet", () => {
    renderShellAt("/fleet");

    // Skip-to-content link is present and addresses the main region.
    const skipLink = screen.getByRole("link", { name: /skip to main content/i });
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute("href", "#main-content");

    // Brand title is rendered (endpoint URL/status pill from the legacy
    // AppShell is intentionally removed per Req 7.8).
    expect(screen.getByText(/operations console/i)).toBeInTheDocument();
    // No endpoint URL is leaked into the shell.
    expect(screen.queryByText(/http:\/\//i)).not.toBeInTheDocument();
    expect(screen.queryByText(/default endpoint|custom endpoint/i)).not.toBeInTheDocument();

    // All four nav links from NAV_ITEMS are present.
    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }

    // Theme toggle from the theme module is mounted by the shell.
    expect(screen.getByTestId("theme-toggle")).toBeInTheDocument();

    // The router outlet rendered the matched route's content.
    expect(screen.getByText("Fleet content")).toBeInTheDocument();
  });

  it("marks the active route's nav link with aria-current=page (non-color distinction signal)", () => {
    renderShellAt("/live");

    const active = screen.getByRole("link", { name: "Live Monitor" });
    expect(active).toHaveAttribute("aria-current", "page");

    // Non-active links must not advertise aria-current.
    for (const item of NAV_ITEMS.filter((nav) => nav.to !== "/live")) {
      const link = screen.getByRole("link", { name: item.label });
      expect(link).not.toHaveAttribute("aria-current", "page");
    }
  });

  it("exposes a main landmark addressable by the skip link", () => {
    renderShellAt("/fleet");

    const main = screen.getByRole("main");
    expect(main).toBeInTheDocument();
    expect(main).toHaveAttribute("id", "main-content");
  });
});

describe("navReducer — exported pure reducer", () => {
  it("`toggle` flips isExpanded", () => {
    expect(navReducer({ isExpanded: false }, { type: "toggle" })).toEqual({
      isExpanded: true,
    });
    expect(navReducer({ isExpanded: true }, { type: "toggle" })).toEqual({
      isExpanded: false,
    });
  });

  it("applying `toggle` twice returns to the original state (involution)", () => {
    const start: { isExpanded: boolean } = { isExpanded: false };
    const after = navReducer(navReducer(start, { type: "toggle" }), {
      type: "toggle",
    });
    expect(after).toEqual(start);

    const startOpen: { isExpanded: boolean } = { isExpanded: true };
    const afterOpen = navReducer(navReducer(startOpen, { type: "toggle" }), {
      type: "toggle",
    });
    expect(afterOpen).toEqual(startOpen);
  });

  it("`selectLink` collapses regardless of prior state", () => {
    expect(navReducer({ isExpanded: true }, { type: "selectLink" })).toEqual({
      isExpanded: false,
    });
    expect(navReducer({ isExpanded: false }, { type: "selectLink" })).toEqual({
      isExpanded: false,
    });
  });

  it("exports a documented initial state with isExpanded === false", () => {
    expect(initialNavState).toEqual({ isExpanded: false });
  });
});
