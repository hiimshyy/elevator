// Feature: ui-ux-responsive-redesign
// Unit tests for the live-region announcer (LiveRegionProvider + useAnnouncer).
//
// Validates: Requirements 6.6, 6.7
//
// Requirement 6.6 (verbatim):
//   WHEN a Data_State changes to error, THE Operations_Console SHALL announce
//   the error through an assertive live region within 1 second of the state
//   change, and the announcement SHALL include a text description of the
//   error.
//
// Requirement 6.7 (verbatim):
//   WHEN a Data_State changes to loading, THE Operations_Console SHALL
//   announce the loading state through a polite live region within 1 second
//   of the state change.
//
// What these tests verify against the existing announcer:
//   1. Two persistent live-region nodes are rendered with the correct
//      aria-live politeness (polite + assertive) and aria-atomic="true" so
//      assistive technologies will pick up DOM mutations.
//   2. Calling `announcePolite(message)` writes the message text into the
//      polite live region and leaves the assertive region untouched
//      (Requirement 6.7: loading announces politely).
//   3. Calling `announceAssertive(message)` writes the message text into the
//      assertive live region and leaves the polite region untouched
//      (Requirement 6.6: error announces assertively with the error text).
//   4. `useAnnouncer` throws a descriptive error when invoked outside of a
//      `LiveRegionProvider`, surfacing a usage mistake at runtime.

import { act, render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveRegionProvider, useAnnouncer } from "../LiveRegionProvider";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/**
 * Provider wrapper used by `renderHook` so the hook under test is mounted
 * inside the live-region context (and so the rendered live-region nodes are
 * available to `screen` queries).
 */
function ProviderWrapper({ children }: { children: ReactNode }): JSX.Element {
  return <LiveRegionProvider>{children}</LiveRegionProvider>;
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("LiveRegionProvider / useAnnouncer (Requirements 6.6, 6.7)", () => {
  // The announcer clears the region and writes the new text on a 0ms timer
  // so that repeating the same message still produces a DOM mutation for
  // assistive technologies. Fake timers let the tests deterministically flush
  // that scheduled write.
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders persistent polite and assertive live regions with correct ARIA wiring", () => {
    render(
      <LiveRegionProvider>
        <div />
      </LiveRegionProvider>
    );

    const polite = screen.getByTestId("live-region-polite");
    const assertive = screen.getByTestId("live-region-assertive");

    // The polite region carries aria-live="polite" so loading announcements
    // wait their turn (Requirement 6.7).
    expect(polite).toHaveAttribute("aria-live", "polite");
    expect(polite).toHaveAttribute("aria-atomic", "true");
    // The assertive region carries aria-live="assertive" so error
    // announcements interrupt (Requirement 6.6).
    expect(assertive).toHaveAttribute("aria-live", "assertive");
    expect(assertive).toHaveAttribute("aria-atomic", "true");

    // Both nodes start empty so no spurious announcement is made on mount.
    expect(polite.textContent).toBe("");
    expect(assertive.textContent).toBe("");
  });

  it("announcePolite places the loading message text in the polite live region (Requirement 6.7)", () => {
    const { result } = renderHook(() => useAnnouncer(), {
      wrapper: ProviderWrapper
    });

    const message = "Loading elevator summaries";

    act(() => {
      result.current.announcePolite(message);
      // Flush the 0ms timer that performs the actual text write.
      vi.runAllTimers();
    });

    // The polite region now carries the loading message text verbatim ...
    expect(screen.getByTestId("live-region-polite").textContent).toBe(message);
    // ... and the assertive region remains empty so no error is falsely
    // signalled to assistive technologies.
    expect(screen.getByTestId("live-region-assertive").textContent).toBe("");
  });

  it("announceAssertive places the error message text in the assertive live region (Requirement 6.6)", () => {
    const { result } = renderHook(() => useAnnouncer(), {
      wrapper: ProviderWrapper
    });

    const message = "Failed to load alerts: network error";

    act(() => {
      result.current.announceAssertive(message);
      // Flush the 0ms timer that performs the actual text write.
      vi.runAllTimers();
    });

    // The assertive region now carries the error description verbatim,
    // satisfying the "announcement SHALL include a text description of the
    // error" clause of Requirement 6.6 ...
    expect(screen.getByTestId("live-region-assertive").textContent).toBe(message);
    // ... and the polite region remains empty so loading state isn't falsely
    // signalled alongside the error.
    expect(screen.getByTestId("live-region-polite").textContent).toBe("");
  });

  it("useAnnouncer throws a descriptive error when used outside a LiveRegionProvider", () => {
    // The provider-less render intentionally throws; silence React's
    // error-boundary console output to keep the test log clean.
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    expect(() => renderHook(() => useAnnouncer())).toThrow(
      "useAnnouncer must be used within a LiveRegionProvider"
    );

    consoleErrorSpy.mockRestore();
  });
});
