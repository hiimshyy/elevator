import { useEffect, useMemo } from "react";

import { useAnnouncer } from "../../a11y";

import "./DataState.css";

// =============================================================================
// DataState — reusable loading/empty/error presentation
// Requirements: 3.8 (reusable primitive), 7.1 (loading indicator visible),
//               7.3 (empty state names missing data),
//               7.4 (error state shows view name + reason + retry).
//
// On transition into `loading` or `error`, the component announces the
// rendered message through the app-level live region exposed by
// `useAnnouncer` (Requirements 6.6, 6.7 — announcement within 1 second of
// the state change).
//
// USAGE
// -----
// `DataState` calls `useAnnouncer`, so it MUST be rendered inside a
// `<LiveRegionProvider>` (mounted at the application root in task 20.1).
// Rendering it outside the provider raises an error at runtime — this is
// intentional so misuse is caught immediately rather than silently
// dropping accessibility announcements.
// =============================================================================

/** The three presentations DataState renders. */
export type DataStatePresentation = "loading" | "empty" | "error";

export interface DataStateProps {
  /** Which presentation to render. */
  state: DataStatePresentation;
  /**
   * Human-readable name of the view this DataState belongs to (e.g.
   * "Fleet Overview", "Alerts"). Used to compose loading/empty/error
   * messages so they always name what the user is waiting on or what
   * failed (Requirement 7.4).
   */
  viewLabel: string;
  /**
   * Plural-noun name of the data that is missing in the empty state
   * (e.g. "alerts", "elevators"). Required by the spec for the empty
   * presentation so messages always name the missing data
   * (Requirement 7.3). Falls back to `viewLabel` if omitted so the empty
   * state still names something.
   */
  missingDataLabel?: string;
  /**
   * Reason for the failure shown in the error state (e.g. "network error",
   * "request timed out"). Surfaced verbatim to the user and included in
   * the assertive announcement (Requirement 6.6).
   */
  errorReason?: string;
  /**
   * When supplied, the error presentation renders a retry control that
   * calls this function. Without it the retry control is omitted so the
   * caller can decide whether retry is meaningful for the view.
   */
  onRetry?: () => void;
  /** Optional extra class for caller-level layout integration. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Message builders — pure functions, exported for testability and reuse.
// ---------------------------------------------------------------------------

/** Build the loading message displayed and announced (politely). */
export function buildLoadingMessage(viewLabel: string): string {
  return `Loading ${viewLabel}…`;
}

/**
 * Build the empty-state message, naming the missing data so the user can
 * disambiguate it from a still-loading view (Requirement 7.3).
 */
export function buildEmptyMessage(
  viewLabel: string,
  missingDataLabel?: string
): string {
  const noun = missingDataLabel ?? viewLabel;
  return `No ${noun} to display`;
}

/**
 * Build the error-state message. Always names the view; appends the
 * caller-supplied reason when present (Requirement 7.4).
 */
export function buildErrorMessage(
  viewLabel: string,
  errorReason?: string
): string {
  if (errorReason && errorReason.trim().length > 0) {
    return `${viewLabel} failed to load: ${errorReason}`;
  }
  return `${viewLabel} failed to load`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataState({
  state,
  viewLabel,
  missingDataLabel,
  errorReason,
  onRetry,
  className,
}: DataStateProps): JSX.Element {
  const { announcePolite, announceAssertive } = useAnnouncer();

  // The displayed message text is also the announced text — keep them
  // in sync so screen-reader and visual users see the same wording.
  const message = useMemo(() => {
    switch (state) {
      case "loading":
        return buildLoadingMessage(viewLabel);
      case "empty":
        return buildEmptyMessage(viewLabel, missingDataLabel);
      case "error":
        return buildErrorMessage(viewLabel, errorReason);
    }
  }, [state, viewLabel, missingDataLabel, errorReason]);

  // Announce on mount and whenever the state transitions. The announcer
  // schedules the DOM write on the next tick so the announcement is
  // delivered well within the 1-second budget defined by Requirements
  // 6.6 (assertive error) and 6.7 (polite loading).
  useEffect(() => {
    if (state === "loading") {
      announcePolite(message);
    } else if (state === "error") {
      announceAssertive(message);
    }
    // Empty state is informational and not on the critical path for
    // assistive announcements; the visible text alone is sufficient.
  }, [state, message, announcePolite, announceAssertive]);

  const rootClass = ["data-state", `data-state--${state}`, className]
    .filter(Boolean)
    .join(" ");

  if (state === "loading") {
    return (
      <div
        className={rootClass}
        role="status"
        aria-live="polite"
        aria-busy="true"
        data-testid="data-state"
        data-state="loading"
      >
        <span
          className="data-state__spinner"
          aria-hidden="true"
          data-testid="data-state-spinner"
        />
        <p className="data-state__message">{message}</p>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div
        className={rootClass}
        role="status"
        data-testid="data-state"
        data-state="empty"
      >
        <p className="data-state__message">{message}</p>
      </div>
    );
  }

  // state === "error"
  return (
    <div
      className={rootClass}
      role="alert"
      data-testid="data-state"
      data-state="error"
    >
      <p className="data-state__message">{message}</p>
      {errorReason && errorReason.trim().length > 0 ? (
        <p className="data-state__detail" data-testid="data-state-reason">
          {errorReason}
        </p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          className="data-state__retry"
          onClick={onRetry}
          data-testid="data-state-retry"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
