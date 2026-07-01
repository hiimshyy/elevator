// Feature: ui-ux-responsive-redesign
// Unit tests for the data-state timing guarantees of `useViewState`.
//
// Validates: Requirements 7.1, 7.2, 7.5
//
// Requirement 7.1 (verbatim):
//   WHILE a Data_State is loading, THE Operations_Console SHALL display a
//   loading indicator for the affected view within 300 milliseconds of the
//   request starting.
//
// Requirement 7.2 (verbatim):
//   IF a Data_State remains loading for more than 30 seconds, THEN THE
//   Operations_Console SHALL stop the loading indicator and display an error
//   message indicating a request timeout with a retry control.
//
// Requirement 7.5 (verbatim):
//   WHEN a user activates the retry control, THE Operations_Console SHALL
//   re-request the data for the affected view and return to the loading
//   Data_State for that view.
//
// What these tests verify against `useViewState`:
//   1. The `showLoadingIndicator` flag stays false strictly before the 300ms
//      grace window elapses and flips to true once it has elapsed
//      (Requirement 7.1 lower-bound + at-300ms boundary).
//   2. A request that resolves before 300ms never flips the indicator on —
//      the indicator timer must have been cleared (Requirement 7.1 anti-
//      flicker behaviour).
//   3. A hung request still in `loading` after 30s is aborted by the
//      watchdog and the hook transitions to `error` with the configured
//      timeout reason, while still exposing a callable retry control
//      (Requirement 7.2).
//   4. Calling `retry()` returns the view to `loading` and re-invokes the
//      fetcher, with previously loaded data preserved across the transition
//      (Requirement 7.5; sanity-check of 7.4 data preservation).
//   5. When the watchdog fires after a successful first load, the resulting
//      `error` state preserves the previously loaded data unchanged (sanity-
//      check of Requirement 7.4 alongside the 7.2 timeout path).

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LOADING_INDICATOR_DELAY_MS,
  DEFAULT_TIMEOUT_MS,
  DEFAULT_TIMEOUT_REASON,
  useViewState
} from "./viewState";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/**
 * Fetcher that never resolves and never rejects on its own. The hook can
 * only leave the loading state via its own abort/watchdog wiring.
 *
 * Honors the abort signal so the 30s watchdog test can reject the in-flight
 * promise once `controller.abort()` is called.
 */
function makeHangingFetcher<T>(): (signal: AbortSignal) => Promise<T> {
  return (signal) =>
    new Promise<T>((_, reject) => {
      signal.addEventListener("abort", () => {
        reject(new DOMException("aborted", "AbortError"));
      });
    });
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("useViewState timing (Requirements 7.1, 7.2, 7.5)", () => {
  // The hook schedules both the 300ms loading-indicator timer and the 30s
  // watchdog via `setTimeout`. Fake timers let each test drive those clocks
  // deterministically; real timers are restored in afterEach so a failing
  // assertion doesn't leak fake timers into other suites.
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // --------------------------------------------------------------------- 7.1
  it("showLoadingIndicator stays false before 300ms and flips true at 300ms (Requirement 7.1)", async () => {
    const fetcher = makeHangingFetcher<string>();

    const { result, unmount } = renderHook(() =>
      useViewState<string>({
        viewLabel: "Fleet Overview",
        fetcher,
        deps: []
      })
    );

    // Immediately after render the hook is in `loading` but the indicator
    // grace window has not started ticking down yet from the consumer's
    // perspective, so the indicator must be hidden.
    expect(result.current.state).toBe("loading");
    expect(result.current.showLoadingIndicator).toBe(false);

    // One millisecond before the 300ms threshold the indicator must still
    // be hidden — the requirement is "within 300ms", not "before 300ms".
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEFAULT_LOADING_INDICATOR_DELAY_MS - 1);
    });
    expect(result.current.state).toBe("loading");
    expect(result.current.showLoadingIndicator).toBe(false);

    // Crossing the 300ms boundary fires the indicator timer; the hook
    // sets showLoadingIndicator=true while still in `loading`.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(result.current.state).toBe("loading");
    expect(result.current.showLoadingIndicator).toBe(true);

    // Unmount cleans up the in-flight controller/watchdog so the never-
    // resolving promise is silently aborted at test teardown.
    unmount();
  });

  // --------------------------------------------------------------------- 7.1
  it("fast resolves under 300ms never show the loading indicator (Requirement 7.1)", async () => {
    // A fetcher that resolves on a 100ms timer — well inside the 300ms
    // grace window, so the indicator timer should be cleared before it
    // ever fires.
    const fetcher = vi.fn<[AbortSignal], Promise<string>>(
      () =>
        new Promise<string>((resolve) => {
          setTimeout(() => resolve("fleet-rows"), 100);
        })
    );

    const { result, unmount } = renderHook(() =>
      useViewState<string>({
        viewLabel: "Fleet Overview",
        fetcher,
        deps: []
      })
    );

    expect(result.current.state).toBe("loading");
    expect(result.current.showLoadingIndicator).toBe(false);

    // Advance just past the fetcher's 100ms timer and flush microtasks so
    // the hook's `await` resolves and dispatches `succeedPopulated`.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.state).toBe("populated");
    expect(result.current.data).toBe("fleet-rows");
    // The 300ms indicator timer must have been cleared on resolve, so the
    // indicator stays hidden — this is the anti-flicker guarantee.
    expect(result.current.showLoadingIndicator).toBe(false);

    // Even if we advanced past the original 300ms mark, no late tick
    // should retroactively flip the indicator on.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.showLoadingIndicator).toBe(false);

    unmount();
  });

  // --------------------------------------------------------------------- 7.2
  it("hung request transitions to error after 30s with retry control (Requirement 7.2)", async () => {
    const fetcher = makeHangingFetcher<string>();

    const { result, unmount } = renderHook(() =>
      useViewState<string>({
        viewLabel: "Alerts",
        fetcher,
        deps: []
      })
    );

    // Just before 30s elapses we must still be in `loading` — the
    // watchdog has not yet fired.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS - 1);
    });
    expect(result.current.state).toBe("loading");

    // Crossing the 30s threshold fires the watchdog, which aborts the
    // in-flight controller. The abort listener rejects the fetcher
    // promise with an AbortError; the catch branch then notices the
    // `timedOut` flag and dispatches `failError` with the timeout reason.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(result.current.state).toBe("error");
    // No prior successful load, so `data` remains the initial null and
    // is not overwritten by the error transition.
    expect(result.current.data).toBeNull();
    // The error message identifies the view (Requirement 7.4) and states
    // the failure reason as the configured timeout reason (Requirement 7.2).
    expect(result.current.error).toContain("Alerts");
    expect(result.current.error).toContain(DEFAULT_TIMEOUT_REASON);
    // The retry control is part of the rendered API surface — Requirement
    // 7.2 explicitly demands the timeout error "with a retry control".
    expect(typeof result.current.retry).toBe("function");
    // The indicator must be torn down once we leave `loading`.
    expect(result.current.showLoadingIndicator).toBe(false);

    unmount();
  });

  // --------------------------------------------------------------------- 7.5
  it("retry() returns to loading and re-invokes the fetcher (Requirement 7.5)", async () => {
    // Counting fetcher: each call resolves after 10ms with a per-call
    // payload so we can distinguish the first and second loads.
    let calls = 0;
    const fetcher = vi.fn<[AbortSignal], Promise<string>>(() => {
      calls += 1;
      const callIndex = calls;
      return new Promise<string>((resolve) => {
        setTimeout(() => resolve(`load-${callIndex}`), 10);
      });
    });

    const { result, unmount } = renderHook(() =>
      useViewState<string>({
        viewLabel: "Fleet Overview",
        fetcher,
        deps: []
      })
    );

    // Resolve the initial load and confirm the populated payload + that
    // the fetcher has been invoked exactly once.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.state).toBe("populated");
    expect(result.current.data).toBe("load-1");
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Activate the retry control. Synchronously (within the act block)
    // the hook must return to the loading state with the previously
    // loaded data preserved (Requirement 7.5 + 7.4 cross-check).
    act(() => {
      result.current.retry();
    });
    expect(result.current.state).toBe("loading");
    expect(result.current.data).toBe("load-1");
    expect(result.current.error).toBeNull();

    // Advance past the second resolve and confirm the fetcher has been
    // invoked a second time and the new payload is displayed.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.state).toBe("populated");
    expect(result.current.data).toBe("load-2");
    expect(fetcher).toHaveBeenCalledTimes(2);

    unmount();
  });

  // ----------------------------------------------------------- 7.4 sanity
  it("error transition after a successful first load preserves the prior data (Requirement 7.4 sanity)", async () => {
    // First call resolves with X after 10ms; second call hangs and
    // honors abort so the 30s watchdog can convert it to a timeout error.
    let callCount = 0;
    const fetcher = vi.fn<[AbortSignal], Promise<string>>((signal) => {
      callCount += 1;
      if (callCount === 1) {
        return new Promise<string>((resolve) => {
          setTimeout(() => resolve("initial-data"), 10);
        });
      }
      return new Promise<string>((_, reject) => {
        signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    });

    const { result, unmount } = renderHook(() =>
      useViewState<string>({
        viewLabel: "Fleet Overview",
        fetcher,
        deps: []
      })
    );

    // First load resolves to the X payload.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.state).toBe("populated");
    expect(result.current.data).toBe("initial-data");

    // Trigger retry; the second call will hang until the watchdog aborts.
    act(() => {
      result.current.retry();
    });
    expect(result.current.state).toBe("loading");
    expect(result.current.data).toBe("initial-data");

    // Drive the 30s watchdog. After it fires the hook must transition to
    // error while leaving the previously loaded data intact (Requirement
    // 7.4: error preserves prior data).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS);
    });

    expect(result.current.state).toBe("error");
    expect(result.current.data).toBe("initial-data");
    expect(result.current.error).toContain("Fleet Overview");
    expect(result.current.error).toContain(DEFAULT_TIMEOUT_REASON);

    unmount();
  });
});
