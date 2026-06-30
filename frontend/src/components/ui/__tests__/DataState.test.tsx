// Feature: ui-ux-responsive-redesign
// Co-located unit tests for the DataState reusable UI primitive.
//
// Validates: Requirements 3.8, 6.6, 6.7, 7.1, 7.3, 7.4
//
// These tests confirm the announcer integration described in task 9.5:
//   - loading      -> polite announcement of the visible message
//   - error        -> assertive announcement of the visible message
//   - empty        -> message names the missing data (Req 7.3)
//   - error        -> message includes the view name + reason; retry is
//                     rendered only when `onRetry` is supplied (Req 7.4)
//   - missing      -> rendering outside a LiveRegionProvider throws
//     provider     (documented contract).

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveRegionProvider } from "../../../a11y";
import { DataState } from "../DataState";

function renderWithProvider(ui: React.ReactElement) {
  return render(<LiveRegionProvider>{ui}</LiveRegionProvider>);
}

describe("DataState (Requirements 3.8, 6.6, 6.7, 7.1, 7.3, 7.4)", () => {
  // The announcer schedules its DOM write on a 0ms timer so identical
  // repeat announcements still produce a DOM mutation. Use fake timers so
  // tests can deterministically flush that scheduled write.
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loading: renders a spinner + visible message and announces politely (Reqs 6.7, 7.1)", () => {
    renderWithProvider(<DataState state="loading" viewLabel="Fleet Overview" />);

    // Flush the scheduled live-region write.
    act(() => {
      vi.runAllTimers();
    });

    // Visible message names the view so users can see what is loading.
    expect(screen.getByTestId("data-state")).toHaveAttribute("data-state", "loading");
    expect(screen.getByTestId("data-state-spinner")).toBeInTheDocument();
    expect(screen.getByTestId("data-state")).toHaveTextContent(/Loading Fleet Overview/i);

    // Polite live region received the same message; assertive remains silent.
    expect(screen.getByTestId("live-region-polite").textContent).toMatch(
      /Loading Fleet Overview/i
    );
    expect(screen.getByTestId("live-region-assertive").textContent).toBe("");
  });

  it("empty: message names the missing data (Req 7.3)", () => {
    renderWithProvider(
      <DataState state="empty" viewLabel="Alerts" missingDataLabel="alerts" />
    );

    act(() => {
      vi.runAllTimers();
    });

    // The visible message names the missing data noun.
    expect(screen.getByTestId("data-state")).toHaveTextContent(/No alerts to display/i);

    // Empty state is not announced through the assertive or polite region.
    expect(screen.getByTestId("live-region-polite").textContent).toBe("");
    expect(screen.getByTestId("live-region-assertive").textContent).toBe("");
  });

  it("empty: falls back to viewLabel when missingDataLabel is omitted", () => {
    renderWithProvider(<DataState state="empty" viewLabel="Alerts" />);

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.getByTestId("data-state")).toHaveTextContent(/No Alerts to display/i);
  });

  it("error: shows view name + reason and announces assertively (Reqs 6.6, 7.4)", () => {
    renderWithProvider(
      <DataState
        state="error"
        viewLabel="Alerts"
        errorReason="network error"
        onRetry={() => undefined}
      />
    );

    act(() => {
      vi.runAllTimers();
    });

    // Visible message contains the view name and the reason.
    const container = screen.getByTestId("data-state");
    expect(container).toHaveAttribute("data-state", "error");
    expect(container).toHaveTextContent(/Alerts failed to load: network error/i);
    expect(screen.getByTestId("data-state-reason")).toHaveTextContent(/network error/i);

    // Retry control is rendered with a sensible accessible name.
    const retry = screen.getByTestId("data-state-retry");
    expect(retry).toBeInTheDocument();
    expect(retry).toHaveAccessibleName(/retry/i);

    // Assertive live region received the same message; polite remains silent.
    expect(screen.getByTestId("live-region-assertive").textContent).toMatch(
      /Alerts failed to load: network error/i
    );
    expect(screen.getByTestId("live-region-polite").textContent).toBe("");
  });

  it("error: does not render retry control when onRetry is not supplied", () => {
    renderWithProvider(
      <DataState state="error" viewLabel="Alerts" errorReason="boom" />
    );

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.queryByTestId("data-state-retry")).toBeNull();
  });

  it("error: clicking the retry control invokes the onRetry callback", () => {
    // fireEvent.click is synchronous and plays nicely with fake timers,
    // unlike userEvent which schedules micro-delays internally.
    const onRetry = vi.fn();

    renderWithProvider(
      <DataState
        state="error"
        viewLabel="Alerts"
        errorReason="boom"
        onRetry={onRetry}
      />
    );

    act(() => {
      vi.runAllTimers();
    });

    fireEvent.click(screen.getByTestId("data-state-retry"));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("transitioning loading -> error re-announces through the assertive region", () => {
    const { rerender } = renderWithProvider(
      <DataState state="loading" viewLabel="Fleet Overview" />
    );

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.getByTestId("live-region-polite").textContent).toMatch(
      /Loading Fleet Overview/i
    );

    rerender(
      <LiveRegionProvider>
        <DataState
          state="error"
          viewLabel="Fleet Overview"
          errorReason="timeout"
        />
      </LiveRegionProvider>
    );

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.getByTestId("live-region-assertive").textContent).toMatch(
      /Fleet Overview failed to load: timeout/i
    );
  });

  it("throws a descriptive error when rendered outside a LiveRegionProvider", () => {
    // Suppress React's error-boundary console output for this expected throw.
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() =>
      render(<DataState state="loading" viewLabel="Fleet Overview" />)
    ).toThrow(/useAnnouncer must be used within a LiveRegionProvider/);

    consoleErrorSpy.mockRestore();
  });
});
