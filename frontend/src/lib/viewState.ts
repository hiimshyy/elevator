import {
  useCallback,
  useEffect,
  useReducer,
  useRef,
  useState,
  type Reducer
} from "react";

// =============================================================================
// View Data-State Reducer and Request Lifecycle — Elevator PDM Operations Console
// Requirements: 7.1, 7.2, 7.4, 7.5
//
// This module exposes three layers:
//
//   1. The `ViewDataState<T>` model and pure transition functions
//      (`startLoading`, `succeedPopulated`, `succeedEmpty`, `failError`,
//      `retry`). These are framework-agnostic and directly testable.
//   2. A `viewStateReducer` (and `ViewAction<T>` union) that wraps the pure
//      transitions in a single dispatch surface for `useReducer`.
//   3. A `useViewState<T>` hook that drives a fetcher through the full
//      request lifecycle: a 300ms loading-indicator grace window
//      (Requirement 7.1), a 30s `AbortController` watchdog that converts a
//      hang into a timeout error (Requirement 7.2), a `failError` transition
//      that preserves prior data and composes a view-named error message
//      (Requirement 7.4), and a `retry` callback that re-issues the request
//      and returns the view to `loading` (Requirement 7.5).
//
// Per the design, `data` and `error` are stored as independent fields so an
// error never blanks previously loaded content. The hook only resolves the
// state machine onto the freshest in-flight request: superseded or
// cleanup-aborted requests are silently dropped, while the 30s watchdog
// surfaces an explicit timeout error.
// =============================================================================

/** The four data-presentation states from the design's ViewDataState model. */
export type DataState = "loading" | "empty" | "error" | "populated";

export interface ViewDataState<T> {
  /** Current data-state. */
  state: DataState;
  /**
   * Most recently loaded data, preserved across error transitions so an
   * error never blanks the view (Requirement 7.4).
   */
  data: T | null;
  /**
   * User-facing error message composed by `failError` — always names the
   * view (Requirement 7.4) and includes the failure reason when available.
   */
  error: string | null;
  /** ISO timestamp of the most recent successful resolution, or null. */
  lastUpdatedAt: string | null;
}

/**
 * Default delay before showing the loading indicator (Requirement 7.1).
 * Suppresses spinner flicker for sub-300ms requests while guaranteeing the
 * indicator is visible by 300ms for any slower request.
 */
export const DEFAULT_LOADING_INDICATOR_DELAY_MS = 300;

/**
 * Default loading watchdog timeout (Requirement 7.2). When a request stays
 * in `loading` for this long, the hook aborts it and transitions to error
 * with the configured timeout reason.
 */
export const DEFAULT_TIMEOUT_MS = 30_000;

/** Reason text stored on the error message when the watchdog fires. */
export const DEFAULT_TIMEOUT_REASON = "request timed out";

/** Build the initial `ViewDataState<T>` (state="loading", no data, no error). */
export function initialViewState<T>(): ViewDataState<T> {
  return {
    state: "loading",
    data: null,
    error: null,
    lastUpdatedAt: null
  };
}

// ---------------------------------------------------------------------------
// Pure transition functions — exported so tests and other reducers can use
// them directly without going through the React reducer.
// ---------------------------------------------------------------------------

/**
 * Transition into the loading state, preserving any previously loaded data
 * (Requirement 7.4: error/retry must not blank `data`). Clears the error
 * field because the caller has chosen to re-run the request.
 */
export function startLoading<T>(prev: ViewDataState<T>): ViewDataState<T> {
  return {
    state: "loading",
    data: prev.data,
    error: null,
    lastUpdatedAt: prev.lastUpdatedAt
  };
}

/** Transition into the populated state with fresh data and a fresh timestamp. */
export function succeedPopulated<T>(data: T, timestamp: string): ViewDataState<T> {
  return {
    state: "populated",
    data,
    error: null,
    lastUpdatedAt: timestamp
  };
}

/**
 * Transition into the empty state. Clears `data` because the latest
 * successful response carried no rows; the empty presentation should not
 * silently render stale rows from a prior request.
 */
export function succeedEmpty<T>(timestamp: string): ViewDataState<T> {
  return {
    state: "empty",
    data: null,
    error: null,
    lastUpdatedAt: timestamp
  };
}

/**
 * Transition into the error state. Preserves the previously loaded `data`
 * unchanged and stores an error message that names the view and includes
 * the failure reason (Requirement 7.4). `lastUpdatedAt` is kept because
 * the previously displayed data is still "as of" that timestamp.
 */
export function failError<T>(
  prev: ViewDataState<T>,
  viewLabel: string,
  reason: string
): ViewDataState<T> {
  return {
    state: "error",
    data: prev.data,
    error: buildViewStateErrorMessage(viewLabel, reason),
    lastUpdatedAt: prev.lastUpdatedAt
  };
}

/**
 * Retry transition (Requirement 7.5) — equivalent to `startLoading`. Kept
 * as a distinct exported helper so call sites can express intent ("retry"
 * versus "initial load") even though the resulting state is the same.
 */
export function retry<T>(prev: ViewDataState<T>): ViewDataState<T> {
  return startLoading(prev);
}

/**
 * Compose an error message that always names the view and, when a
 * non-empty reason is provided, appends it after a colon (Requirement 7.4).
 */
export function buildViewStateErrorMessage(viewLabel: string, reason: string): string {
  const trimmedReason = typeof reason === "string" ? reason.trim() : "";
  if (trimmedReason.length === 0) {
    return `${viewLabel} failed to load`;
  }
  return `${viewLabel} failed to load: ${trimmedReason}`;
}

// ---------------------------------------------------------------------------
// Reducer — thin dispatch shim over the pure transition functions.
// ---------------------------------------------------------------------------

export type ViewAction<T> =
  | { type: "startLoading" }
  | { type: "succeedPopulated"; data: T; timestamp: string }
  | { type: "succeedEmpty"; timestamp: string }
  | { type: "failError"; viewLabel: string; reason: string };

export function viewStateReducer<T>(
  prev: ViewDataState<T>,
  action: ViewAction<T>
): ViewDataState<T> {
  switch (action.type) {
    case "startLoading":
      return startLoading(prev);
    case "succeedPopulated":
      return succeedPopulated<T>(action.data, action.timestamp);
    case "succeedEmpty":
      return succeedEmpty<T>(action.timestamp);
    case "failError":
      return failError(prev, action.viewLabel, action.reason);
  }
}

// ---------------------------------------------------------------------------
// useViewState hook — drives a fetcher through the full request lifecycle.
// ---------------------------------------------------------------------------

export interface UseViewStateOptions<T> {
  /**
   * Human-readable name of the view (e.g. "Fleet Overview", "Alerts").
   * Inserted into error messages so the user is never left wondering which
   * view failed (Requirement 7.4).
   */
  viewLabel: string;
  /**
   * Fetcher invoked on mount, when `deps` change, and on each retry. It
   * receives an `AbortSignal` that fires on supersede, unmount, or the 30s
   * watchdog expiry; well-behaved fetchers pass the signal to `fetch` so
   * the abort is honored end-to-end.
   */
  fetcher: (signal: AbortSignal) => Promise<T>;
  /**
   * Optional predicate to classify a resolved value as empty. When
   * provided and it returns true, the hook dispatches `succeedEmpty`
   * instead of `succeedPopulated` so the empty presentation can render.
   */
  isEmpty?: (data: T) => boolean;
  /** Override the 300ms loading-indicator grace window (Requirement 7.1). */
  loadingIndicatorDelayMs?: number;
  /** Override the 30s watchdog timeout (Requirement 7.2). */
  timeoutMs?: number;
  /** Reason text used in the error message when the watchdog fires. */
  timeoutReason?: string;
  /**
   * Re-run the fetcher whenever any value in this array changes. Treated
   * as the dependency list for the internal effect; pass an empty array to
   * fetch only once on mount.
   */
  deps?: ReadonlyArray<unknown>;
}

export interface UseViewStateResult<T> extends ViewDataState<T> {
  /**
   * True once the loading-indicator delay has elapsed (default 300ms)
   * while `state === "loading"`. UI should branch on this flag to suppress
   * the spinner for sub-300ms requests while still guaranteeing the
   * indicator is shown by 300ms for slower requests (Requirement 7.1).
   */
  showLoadingIndicator: boolean;
  /**
   * Retry control — cancels any in-flight request, re-issues the fetcher,
   * and returns the view to loading (Requirement 7.5).
   */
  retry: () => void;
}

/**
 * React hook that drives a fetcher through the documented request
 * lifecycle (loading -> populated | empty | error) with the timing
 * guarantees from Requirements 7.1, 7.2, 7.4, 7.5.
 *
 * USAGE
 * -----
 * ```tsx
 * const fleet = useViewState<ElevatorSummary[]>({
 *   viewLabel: "Fleet Overview",
 *   fetcher: (signal) => listElevators(signal),
 *   isEmpty: (rows) => rows.length === 0,
 *   deps: [apiBaseUrl, apiKey],
 * });
 *
 * if (fleet.state === "loading" && fleet.showLoadingIndicator) return <Spinner />;
 * if (fleet.state === "error")  return <Error message={fleet.error} onRetry={fleet.retry} />;
 * if (fleet.state === "empty")  return <Empty />;
 * return <FleetGrid rows={fleet.data ?? []} />;
 * ```
 */
export function useViewState<T>(options: UseViewStateOptions<T>): UseViewStateResult<T> {
  const {
    viewLabel,
    fetcher,
    isEmpty,
    loadingIndicatorDelayMs = DEFAULT_LOADING_INDICATOR_DELAY_MS,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    timeoutReason = DEFAULT_TIMEOUT_REASON,
    deps = []
  } = options;

  // useReducer's generic inference doesn't cope with a generic reducer that
  // takes `ViewAction<T>`, so we widen the reducer to a concrete type for the
  // current T and seed the initial state through `initialViewState<T>()`.
  // useReducer's generic inference doesn't cope with a generic reducer that
  // takes `ViewAction<T>`, so we widen the reducer to a concrete type for the
  // current T and seed the initial state through `initialViewState<T>()`.
  const typedReducer = viewStateReducer as Reducer<ViewDataState<T>, ViewAction<T>>;
  const [state, dispatch] = useReducer(typedReducer, initialViewState<T>());

  const [showLoadingIndicator, setShowLoadingIndicator] = useState(false);

  // Latest config in refs so the retry callback never closes over stale
  // values when the parent re-renders without re-running the effect.
  const fetcherRef = useRef(fetcher);
  const isEmptyRef = useRef(isEmpty);
  const viewLabelRef = useRef(viewLabel);
  const timeoutReasonRef = useRef(timeoutReason);
  const loadingDelayMsRef = useRef(loadingIndicatorDelayMs);
  const timeoutMsRef = useRef(timeoutMs);

  useEffect(() => {
    fetcherRef.current = fetcher;
    isEmptyRef.current = isEmpty;
    viewLabelRef.current = viewLabel;
    timeoutReasonRef.current = timeoutReason;
    loadingDelayMsRef.current = loadingIndicatorDelayMs;
    timeoutMsRef.current = timeoutMs;
  });

  // Active request handles. Each `runFetch` call owns exactly one
  // AbortController, one indicator timer, and one watchdog timer.
  const controllerRef = useRef<AbortController | null>(null);
  const indicatorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const watchdogTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (indicatorTimerRef.current !== null) {
      clearTimeout(indicatorTimerRef.current);
      indicatorTimerRef.current = null;
    }
    if (watchdogTimerRef.current !== null) {
      clearTimeout(watchdogTimerRef.current);
      watchdogTimerRef.current = null;
    }
  }, []);

  const cancelInFlight = useCallback(() => {
    if (controllerRef.current !== null) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    clearTimers();
  }, [clearTimers]);

  const runFetch = useCallback(() => {
    // Cancel any in-flight request first so the prior promise's catch
    // branch falls into the silent-abort path rather than racing the new
    // request's dispatch.
    cancelInFlight();

    dispatch({ type: "startLoading" });
    setShowLoadingIndicator(false);

    const controller = new AbortController();
    controllerRef.current = controller;

    // Local flag that tells the catch branch how to interpret an abort:
    // user/cleanup aborts are silent, watchdog aborts become a timeout
    // error (Requirement 7.2).
    let timedOut = false;

    // Requirement 7.1: schedule the loading indicator to appear within
    // the configured delay (300ms by default). If the request resolves
    // first we cancel this timer, suppressing spinner flicker.
    indicatorTimerRef.current = setTimeout(() => {
      indicatorTimerRef.current = null;
      // Guard against late ticks after a resolution/abort cleared things.
      if (controllerRef.current === controller && !controller.signal.aborted) {
        setShowLoadingIndicator(true);
      }
    }, loadingDelayMsRef.current);

    // Requirement 7.2: 30s watchdog. On expiry, abort the request and
    // mark the abort as a timeout so the catch branch dispatches
    // `failError` with the configured timeout reason.
    watchdogTimerRef.current = setTimeout(() => {
      watchdogTimerRef.current = null;
      if (controllerRef.current === controller && !controller.signal.aborted) {
        timedOut = true;
        controller.abort();
      }
    }, timeoutMsRef.current);

    void (async () => {
      try {
        const data = await fetcherRef.current(controller.signal);

        // The request may have been superseded (new retry, deps change,
        // or unmount) while awaiting. Drop the result so the UI never
        // jumps back to stale data.
        if (controller.signal.aborted) {
          return;
        }

        clearTimers();
        controllerRef.current = null;
        setShowLoadingIndicator(false);

        const timestamp = new Date().toISOString();
        const empty = isEmptyRef.current ? isEmptyRef.current(data) : false;

        if (empty) {
          dispatch({ type: "succeedEmpty", timestamp });
        } else {
          dispatch({ type: "succeedPopulated", data, timestamp });
        }
      } catch (err) {
        // Silent path for cleanup/retry aborts — the watchdog path sets
        // `timedOut` so we can still surface a timeout error here.
        if (controller.signal.aborted && !timedOut) {
          return;
        }

        clearTimers();
        controllerRef.current = null;
        setShowLoadingIndicator(false);

        const reason = timedOut
          ? timeoutReasonRef.current
          : err instanceof Error && err.message.length > 0
            ? err.message
            : "unknown error";

        dispatch({
          type: "failError",
          viewLabel: viewLabelRef.current,
          reason
        });
      }
    })();
  }, [cancelInFlight, clearTimers]);

  // Run on mount and whenever the caller's `deps` change. The cleanup
  // aborts any in-flight request and clears timers so a fast re-mount
  // never leaves a dangling watchdog or indicator timer alive.
  useEffect(() => {
    runFetch();
    return cancelInFlight;
    // The caller-provided `deps` are the canonical dependency list for
    // re-fetching; runFetch itself is stable across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const retryCallback = useCallback(() => {
    runFetch();
  }, [runFetch]);

  return {
    ...state,
    showLoadingIndicator,
    retry: retryCallback
  };
}
