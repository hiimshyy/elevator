import type { HTMLAttributes, ReactNode } from "react";
import "./Card.css";

// =============================================================================
// Card — token-driven surface / elevation primitive
// Requirements: 3.8
// Replaces the legacy `.card`, `.fleet-card`, `.summary-card`, `.panel`, and
// `.workflow-card` literal styling in `index.css`. All visual values come
// from CSS custom-property tokens defined in `styles/tokens.css`.
// =============================================================================

/** Allowed elevation variants, mapped to `--elevation-1/2/3` in tokens.css. */
export type CardElevation = "flat" | "raised" | "overlay";

/** Valid heading levels for the card's auto-rendered title. */
export type CardHeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;

/**
 * Props for the Card primitive.
 *
 * Extends the standard `<div>` attributes so consumers can attach any normal
 * div prop (e.g. `id`, `role`, `data-*`, `aria-*`, event handlers). Because
 * the API uses `title` as a `ReactNode` slot for the visible heading, the
 * native string-only `title` attribute is omitted from the inherited type.
 */
export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  /** Primary content rendered inside the card body. */
  children: ReactNode;
  /**
   * Optional heading content. Rendered inside a semantic heading element
   * whose level is controlled by `headingLevel` (default `2`). Ignored when
   * a fully custom `header` slot is supplied.
   */
  title?: ReactNode;
  /**
   * Optional custom header slot. Takes precedence over `title` when present
   * and is rendered inside the same header region. Use this when the header
   * needs more than a simple heading (e.g. heading + action).
   */
  header?: ReactNode;
  /** Optional footer content rendered below the body. */
  footer?: ReactNode;
  /**
   * Visual elevation level.
   * - `"flat"`    → `--elevation-1` (low ambient depth)
   * - `"raised"`  → `--elevation-2` (default surface)
   * - `"overlay"` → `--elevation-3` (modal / floating surface)
   */
  elevation?: CardElevation;
  /**
   * Heading level for the auto-rendered `title`. Defaults to `2`.
   * Only consulted when `title` is provided and `header` is not.
   */
  headingLevel?: CardHeadingLevel;
}

const ELEVATION_CLASS: Record<CardElevation, string> = {
  flat: "ui-card--elevation-flat",
  raised: "ui-card--elevation-raised",
  overlay: "ui-card--elevation-overlay",
};

/**
 * Card — token-driven surface that hosts grouped content with an optional
 * heading, custom header slot, and footer. The default elevation matches the
 * raised treatment used by the existing `.card` / `.fleet-card` / `.panel`
 * styles it replaces.
 */
export function Card({
  children,
  title,
  header,
  footer,
  elevation = "raised",
  headingLevel = 2,
  className,
  ...rest
}: CardProps): JSX.Element {
  const classes = ["ui-card", ELEVATION_CLASS[elevation], className]
    .filter(Boolean)
    .join(" ");

  const HeadingTag = `h${headingLevel}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
  const hasHeader = header !== undefined || title !== undefined;

  return (
    <div className={classes} {...rest}>
      {hasHeader ? (
        <div className="ui-card__header">
          {header !== undefined ? (
            header
          ) : (
            <HeadingTag className="ui-card__title">{title}</HeadingTag>
          )}
        </div>
      ) : null}
      <div className="ui-card__body">{children}</div>
      {footer !== undefined ? (
        <div className="ui-card__footer">{footer}</div>
      ) : null}
    </div>
  );
}
