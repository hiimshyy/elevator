import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

import { useBreakpoint, type LayoutDescriptor } from "../../hooks/useBreakpoint";

import "./PageContainer.css";

// =============================================================================
// PageContainer / ResponsiveGrid / ResponsiveLayout
// Token-driven responsive layout wrapper for redesigned routes.
//
// Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8
//
// Behavior summary (driven entirely by `useBreakpoint()`'s LayoutDescriptor —
// thresholds and column math live there, never duplicated here):
//   - Mobile (< 640px):   single column of primary content              (Req 4.1)
//   - Tablet (< 1024px):  at most two columns of multi-card content     (Req 4.2)
//   - Desktop / Large:    multi-column grid up to the descriptor's
//                         columnCount, optionally capped via `columns` / `maxColumns`.
//   - Large_Desktop (>= 1440px): content region capped at 1440px and
//                         centered horizontally (margin-inline: auto)   (Req 4.3)
//   - >= 320px:           no horizontal page scroll                     (Req 4.4)
//   - < 320px:            single column + horizontal page scroll
//                         permitted on the container                    (Req 4.8)
//   - Column count and content-cap toggle only when crossing the
//     defined Breakpoint thresholds (`useBreakpoint`'s matchMedia
//     listeners fire at 640 / 1024 / 1440)                              (Req 4.6)
//   - Reflow is pure CSS — no JS animation — so it completes well
//     within the 500ms budget                                            (Req 4.7)
//
// Wiring into App.tsx (mounting PageContainer inside the NavigationShell
// `<main>`) is deferred to task 20.1.
//
// API surface
// -----------
//   <PageContainer>{children}</PageContainer>
//     -> Render arbitrary content with the responsive content-cap +
//        horizontal-scroll treatment. The caller composes its own grid
//        (typically via ResponsiveGrid or Card stacks).
//
//   <PageContainer columns={3}>{children}</PageContainer>
//     -> Same wrapper, but children are auto-wrapped in a ResponsiveGrid
//        capped at `min(columns, descriptor.columnCount)`.
//
//   <ResponsiveGrid maxColumns={2}>{children}</ResponsiveGrid>
//     -> Standalone multi-column grid (no content cap) that follows the
//        breakpoint's `columnCount`, optionally capped to a caller-preferred
//        maximum.
//
//   ResponsiveLayout
//     -> Alias of PageContainer kept for parity with the design diagram
//        (`ResponsiveLayout/PageContainer`).
//
// Data attributes exposed on the rendered roots so integration tests
// (task 13.2) can assert behavior without depending on computed CSS:
//   - `data-breakpoint`               -> descriptor.breakpoint
//   - `data-columns`                  -> effective column count after caps
//   - `data-content-max-width`        -> "1440" at Large_Desktop, "none" elsewhere
//   - `data-allow-horizontal-scroll`  -> "true" only sub-320px, "false" >= 320px
// =============================================================================

/**
 * Names of the CSS custom properties the component writes inline. Kept as
 * constants so the CSS file and the TS file cannot drift.
 */
const COLUMNS_CUSTOM_PROPERTY = "--page-container-columns";
const MAX_WIDTH_CUSTOM_PROPERTY = "--page-container-max-width";

/**
 * Compute the effective column count for a render: the breakpoint's natural
 * column count, optionally capped by a caller-supplied `maxColumns`. Always
 * returns at least 1 so the resulting `repeat(N, ...)` is valid CSS.
 *
 * Non-integer or non-finite `maxColumns` values are ignored (treated as
 * "no cap"); this keeps the component safe against malformed props without
 * a runtime throw.
 */
function resolveColumns(
  descriptorColumns: number,
  maxColumns: number | undefined
): number {
  const baseColumns = Math.max(1, Math.trunc(descriptorColumns) || 1);
  if (typeof maxColumns !== "number" || !Number.isFinite(maxColumns)) {
    return baseColumns;
  }
  const cap = Math.max(1, Math.trunc(maxColumns));
  return Math.min(cap, baseColumns);
}

/**
 * Build the inline style object that carries the descriptor-driven CSS
 * custom properties (content max-width + column count) on top of any
 * caller-provided `style`. Returns a fresh object so callers' style refs
 * remain immutable.
 */
function buildContainerStyle(
  style: CSSProperties | undefined,
  descriptor: LayoutDescriptor,
  effectiveColumns: number | null
): CSSProperties {
  const next: Record<string, string | number> = { ...(style as Record<string, string | number> | undefined) };
  if (descriptor.contentMaxWidth !== null) {
    next[MAX_WIDTH_CUSTOM_PROPERTY] = `${descriptor.contentMaxWidth}px`;
  }
  if (effectiveColumns !== null) {
    next[COLUMNS_CUSTOM_PROPERTY] = effectiveColumns;
  }
  return next as CSSProperties;
}

function buildGridStyle(style: CSSProperties | undefined, effectiveColumns: number): CSSProperties {
  const next: Record<string, string | number> = { ...(style as Record<string, string | number> | undefined) };
  next[COLUMNS_CUSTOM_PROPERTY] = effectiveColumns;
  return next as CSSProperties;
}

function joinClassNames(...parts: Array<string | undefined | false | null>): string {
  return parts.filter((part): part is string => typeof part === "string" && part.length > 0).join(" ");
}

// ---------------------------------------------------------------------------
// PageContainer
// ---------------------------------------------------------------------------

/**
 * Props accepted by {@link PageContainer}. Extends standard `<div>` attributes
 * so callers can attach any normal DOM prop (id, role, aria-*, data-*, event
 * handlers). The native string-only `children` attribute is replaced with the
 * React `ReactNode` so JSX children compose normally.
 */
export interface PageContainerProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** Primary content rendered inside the container. */
  children: ReactNode;
  /**
   * Optional maximum number of grid columns the caller wishes to render.
   *
   * - When omitted, the container renders `children` as-is (the caller is
   *   responsible for composing its own layout — typically with one or more
   *   {@link ResponsiveGrid} children, or freeform stacks).
   * - When provided, the container wraps `children` in a single
   *   {@link ResponsiveGrid} capped at
   *   `min(columns, descriptor.columnCount)`.
   *
   * Non-finite or non-integer values are ignored.
   */
  columns?: number;
}

/**
 * Responsive page-level wrapper used by every redesigned route.
 *
 * Owns the content-cap (1440px at Large_Desktop, Req 4.3) and the sub-320
 * horizontal-scroll behavior (Req 4.8). Defers all column math to
 * `useBreakpoint()` so threshold logic lives in exactly one place.
 */
export function PageContainer({
  children,
  columns,
  className,
  style,
  ...rest
}: PageContainerProps): JSX.Element {
  const descriptor = useBreakpoint();
  const wrapInGrid = typeof columns === "number" && Number.isFinite(columns);
  const effectiveColumns = wrapInGrid
    ? resolveColumns(descriptor.columnCount, columns)
    : resolveColumns(descriptor.columnCount, undefined);

  const inlineStyle = buildContainerStyle(
    style,
    descriptor,
    // Only emit the columns custom property when we actually render a grid
    // — otherwise the value would be a no-op and could mislead test readers.
    wrapInGrid ? effectiveColumns : null
  );

  const classes = joinClassNames("page-container", className);

  return (
    <div
      className={classes}
      style={inlineStyle}
      data-breakpoint={descriptor.breakpoint}
      data-columns={effectiveColumns}
      data-content-max-width={descriptor.contentMaxWidth === null ? "none" : String(descriptor.contentMaxWidth)}
      data-allow-horizontal-scroll={descriptor.allowHorizontalScroll ? "true" : "false"}
      {...rest}
    >
      {wrapInGrid ? <ResponsiveGrid maxColumns={columns}>{children}</ResponsiveGrid> : children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ResponsiveGrid
// ---------------------------------------------------------------------------

/** Props accepted by {@link ResponsiveGrid}. */
export interface ResponsiveGridProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** Cards or other content laid out by the grid. */
  children: ReactNode;
  /**
   * Optional cap on the rendered column count.
   *
   * When provided, the grid renders `min(maxColumns, descriptor.columnCount)`
   * columns. When omitted, the grid renders exactly
   * `descriptor.columnCount` columns. Non-finite or non-integer values are
   * ignored.
   */
  maxColumns?: number;
}

/**
 * Multi-column responsive grid driven by the active breakpoint's
 * `columnCount`. Uses `grid-template-columns: repeat(N, minmax(0, 1fr))` so
 * grid items can shrink below their intrinsic min-width — required to keep
 * the page from horizontally overflowing at >= 320px (Req 4.4).
 */
export function ResponsiveGrid({
  children,
  maxColumns,
  className,
  style,
  ...rest
}: ResponsiveGridProps): JSX.Element {
  const descriptor = useBreakpoint();
  const effectiveColumns = resolveColumns(descriptor.columnCount, maxColumns);
  const inlineStyle = buildGridStyle(style, effectiveColumns);
  const classes = joinClassNames("responsive-grid", className);

  return (
    <div
      className={classes}
      style={inlineStyle}
      data-breakpoint={descriptor.breakpoint}
      data-columns={effectiveColumns}
      {...rest}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compatibility aliases
// ---------------------------------------------------------------------------

/**
 * Alias of {@link PageContainer}. The design diagram refers to this surface as
 * `ResponsiveLayout/PageContainer`; both names resolve to the same component
 * so call sites can use whichever reads better in context.
 */
export const ResponsiveLayout = PageContainer;
