/**
 * Unit tests for StatusBadge component.
 *
 * Validates: Requirements 3.6, 3.7, 3.8, 6.3
 *
 * Confirms that the badge renders all four signals (color via class hook,
 * icon glyph, visible text label, and shape) for every StatusState and
 * honours its API (`labelOverride`, `className`, pass-through props).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "../StatusBadge";
import { STATUS_VISUALS, type StatusState } from "../statusState";

const ALL_STATES: StatusState[] = ["healthy", "warning", "critical", "unknown"];

describe("StatusBadge", () => {
  it("renders the icon glyph and default label for every state", () => {
    for (const state of ALL_STATES) {
      const { unmount } = render(<StatusBadge state={state} data-testid="badge" />);
      const badge = screen.getByTestId("badge");
      const visual = STATUS_VISUALS[state];

      // Visible icon glyph (non-color signal #1)
      expect(badge.textContent).toContain(visual.icon);
      // Visible text label (non-color signal #2)
      expect(badge.textContent).toContain(visual.label);
      // Shape class hook (non-color signal #3) — drives the CSS outline.
      expect(badge.className).toContain(`status-badge--shape-${visual.shape}`);
      // State class hook drives the color token assignment.
      expect(badge.className).toContain(`status-badge--state-${state}`);
      // data-* attributes expose state + shape for consumers/tests.
      expect(badge.getAttribute("data-state")).toBe(state);
      expect(badge.getAttribute("data-shape")).toBe(visual.shape);

      unmount();
    }
  });

  it("renders labelOverride in place of the default label while keeping the icon and shape", () => {
    render(
      <StatusBadge state="critical" labelOverride="Overload" data-testid="badge" />
    );
    const badge = screen.getByTestId("badge");
    const visual = STATUS_VISUALS.critical;

    expect(badge.textContent).toContain("Overload");
    expect(badge.textContent).not.toContain(visual.label);
    // Icon and shape (non-color signals) remain intact.
    expect(badge.textContent).toContain(visual.icon);
    expect(badge.className).toContain(`status-badge--shape-${visual.shape}`);
  });

  it("composes caller-supplied className with the badge base classes", () => {
    render(
      <StatusBadge state="healthy" className="extra-class" data-testid="badge" />
    );
    const badge = screen.getByTestId("badge");

    expect(badge.className).toContain("status-badge");
    expect(badge.className).toContain("status-badge--state-healthy");
    expect(badge.className).toContain("extra-class");
  });

  it("forwards arbitrary HTML attributes to the rendered span", () => {
    render(
      <StatusBadge
        state="warning"
        id="my-badge"
        title="Sensor drift"
        data-testid="badge"
      />
    );
    const badge = screen.getByTestId("badge");
    expect(badge.tagName).toBe("SPAN");
    expect(badge.id).toBe("my-badge");
    expect(badge.getAttribute("title")).toBe("Sensor drift");
  });

  it("marks the icon as aria-hidden so the visible label is the sole accessible name", () => {
    render(<StatusBadge state="unknown" data-testid="badge" />);
    const badge = screen.getByTestId("badge");
    const icon = badge.querySelector(".status-badge__icon");
    expect(icon).not.toBeNull();
    expect(icon?.getAttribute("aria-hidden")).toBe("true");
  });
});
