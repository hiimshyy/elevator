import { type HTMLAttributes } from "react";
import { getStatusVisual, type StatusState } from "./statusState";
import "./StatusBadge.css";

/**
 * Props for {@link StatusBadge}.
 *
 * Validates: Requirements 3.6, 3.7, 3.8, 6.3
 */
export interface StatusBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** Canonical status state — drives color, icon, label, and shape. */
  state: StatusState;
  /**
   * Optional override for the visible text label. When omitted the default
   * label from the status-state mapper is rendered (e.g. "Healthy").
   * The override never replaces the icon or shape, so the non-color signals
   * remain intact.
   */
  labelOverride?: string;
  /** Extra class names to compose with the badge class set. */
  className?: string;
}

/**
 * `StatusBadge` — token-driven status indicator for the Elevator PDM
 * Operations Console.
 *
 * Renders all four signals defined by the status-state mapper:
 *  - color (via `--color-status-*` background and `--color-status-*-on` text)
 *  - icon (visible unicode glyph, unique per state)
 *  - label (visible text, unique per state by default)
 *  - shape (pill / triangle / diamond / square applied via CSS)
 *
 * The badge therefore differs from every other state in at least three
 * non-color attributes — satisfying the "non-color signal" acceptance
 * criteria (Requirements 3.6, 3.7, 6.3).
 *
 * The component renders as a `<span>` and accepts pass-through HTML
 * attributes (e.g. `id`, `title`, `data-*`, event handlers).
 */
export function StatusBadge({
  state,
  labelOverride,
  className,
  ...rest
}: StatusBadgeProps): JSX.Element {
  const visual = getStatusVisual(state);
  const label = labelOverride ?? visual.label;

  const classes = [
    "status-badge",
    `status-badge--state-${state}`,
    `status-badge--shape-${visual.shape}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span
      {...rest}
      className={classes}
      data-state={state}
      data-shape={visual.shape}
    >
      <span className="status-badge__icon" aria-hidden="true">
        {visual.icon}
      </span>
      <span className="status-badge__label">{label}</span>
    </span>
  );
}

export default StatusBadge;
