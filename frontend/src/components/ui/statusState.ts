/**
 * Status-state mapper for the Elevator PDM Operations Console.
 *
 * Defines the four canonical status states and their visual treatments,
 * and maps domain values from the API to a StatusState.
 *
 * Each state differs from the other three by color, icon, label, AND shape
 * to satisfy non-color signaling requirements (Requirements 3.6, 3.7, 6.3).
 */

// ---------------------------------------------------------------------------
// Core types
// ---------------------------------------------------------------------------

export type StatusState = "healthy" | "warning" | "critical" | "unknown";

export interface StatusVisual {
  /** CSS custom-property reference for the state's color. */
  color: string;
  /** Unicode glyph that acts as a non-color visual signal. Unique per state. */
  icon: string;
  /** Human-readable label. Unique per state. */
  label: string;
  /** Outline shape variant for the badge container. Unique per state. */
  shape: "pill" | "diamond" | "triangle" | "square";
}

// ---------------------------------------------------------------------------
// Visual treatment map
// ---------------------------------------------------------------------------

/**
 * Map of every StatusState to its visual treatment.
 *
 * Each entry differs from every other entry in icon, label, and shape
 * in addition to the color token, satisfying Requirement 3.7.
 */
export const STATUS_VISUALS: Record<StatusState, StatusVisual> = {
  healthy: {
    color: "var(--color-status-healthy)",
    icon: "✓",       // checkmark — distinct non-color glyph
    label: "Healthy",
    shape: "pill",   // rounded pill — distinct outline
  },
  warning: {
    color: "var(--color-status-warning)",
    icon: "⚠",       // warning sign — distinct non-color glyph
    label: "Warning",
    shape: "triangle", // triangle — distinct outline
  },
  critical: {
    color: "var(--color-status-critical)",
    icon: "✕",       // cross — distinct non-color glyph
    label: "Critical",
    shape: "diamond", // diamond — distinct outline
  },
  unknown: {
    color: "var(--color-status-unknown)",
    icon: "?",        // question mark — distinct non-color glyph
    label: "Unknown",
    shape: "square",  // square — distinct outline
  },
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/**
 * Return the StatusVisual for a given state.
 * Pure function; no side effects.
 */
export function getStatusVisual(state: StatusState): StatusVisual {
  return STATUS_VISUALS[state];
}

// ---------------------------------------------------------------------------
// Domain-to-status mappers
// ---------------------------------------------------------------------------

/**
 * Map an ElevatorSummary's `status` string and `latest_health_score` number
 * to a StatusState.
 *
 * Mapping rules (in priority order):
 *  1. status === "CRITICAL" | "OVERLOAD"  → critical
 *  2. status === "WARNING"                → warning
 *  3. healthScore >= 80                   → healthy
 *  4. healthScore >= 50                   → warning
 *  5. healthScore < 50 (and not null)     → critical
 *  6. status === null and score === null  → unknown
 *  7. Any unrecognised status string      → unknown
 *
 * Pure function; no side effects.
 */
export function mapElevatorStatusToState(
  status: string | null,
  healthScore: number | null
): StatusState {
  // Explicit critical statuses take highest priority.
  if (status === "CRITICAL" || status === "OVERLOAD") {
    return "critical";
  }

  // Explicit warning status.
  if (status === "WARNING") {
    return "warning";
  }

  // If status is null or something unrecognised, fall back to health score.
  if (healthScore !== null) {
    if (healthScore >= 80) return "healthy";
    if (healthScore >= 50) return "warning";
    return "critical";
  }

  // Both status and score are null/indeterminate.
  return "unknown";
}

/**
 * Map an AlertRecord's `severity` string to a StatusState.
 *
 * Mapping rules:
 *  - "EMERGENCY" | "CRITICAL" → critical
 *  - "WARNING"                → warning
 *  - null                     → unknown
 *  - anything else            → unknown
 *
 * Pure function; no side effects.
 */
export function mapAlertSeverityToState(severity: string | null): StatusState {
  if (severity === "EMERGENCY" || severity === "CRITICAL") {
    return "critical";
  }

  if (severity === "WARNING") {
    return "warning";
  }

  return "unknown";
}

/**
 * Map a MaintenanceRecord's `status` string to a StatusState.
 *
 * Mapping rules:
 *  - "completed"  → healthy
 *  - "scheduled"  → warning
 *  - "cancelled"  → critical
 *  - "pending"    → unknown
 *  - null / other → unknown
 *
 * Pure function; no side effects.
 */
export function mapMaintenanceStatusToState(status: string | null): StatusState {
  switch (status) {
    case "completed":
      return "healthy";
    case "scheduled":
      return "warning";
    case "cancelled":
      return "critical";
    case "pending":
      return "unknown";
    default:
      return "unknown";
  }
}

// ---------------------------------------------------------------------------
// WebSocket connection state
// ---------------------------------------------------------------------------

/** The three canonical connection states for a live WebSocket feed. */
export type ConnectionState = "connected" | "connecting" | "disconnected";

/**
 * Map a ConnectionState to a StatusState.
 *
 * Mapping rules:
 *  - "connected"    → healthy  (green / checkmark / pill)
 *  - "connecting"   → warning  (amber / ⚠ / triangle)
 *  - "disconnected" → critical (red / ✕ / diamond)
 *
 * Pure function; no side effects.
 */
export function mapConnectionStateToState(connectionState: ConnectionState): StatusState {
  switch (connectionState) {
    case "connected":
      return "healthy";
    case "connecting":
      return "warning";
    case "disconnected":
      return "critical";
  }
}
