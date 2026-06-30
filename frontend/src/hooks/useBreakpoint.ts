import { useSyncExternalStore } from "react";

// =============================================================================
// Breakpoint classifier and hook — Elevator PDM Operations Console
// Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.8, 5.1, 5.2
//
// This module exposes two surfaces:
//   1. `classifyWidth(width)` — a pure function that maps a viewport width (in
//      CSS px) to its Breakpoint and a full layout descriptor. Exported so the
//      property test in task 7.2 can target it directly without touching the
//      DOM.
//   2. `useBreakpoint()` — a React hook backed by `window.matchMedia` listeners
//      at the 640 / 1024 / 1440 thresholds (design's responsive table). It
//      re-renders only when a threshold is crossed (Requirement 4.6) and falls
//      back to a desktop default when no `window` is available (SSR / tests
//      without a DOM).
// =============================================================================

export type Breakpoint = "mobile" | "tablet" | "desktop" | "large";

/**
 * Whether the primary navigation is collapsed behind a menu control
 * ("collapsible") or shown as a persistent sidebar ("persistent").
 */
export type NavMode = "collapsible" | "persistent";

export interface LayoutDescriptor {
  /** Active Breakpoint band. */
  breakpoint: Breakpoint;
  /**
   * Primary column count for content cards (Requirements 4.1, 4.2):
   *  - mobile (incl. sub-320): 1
   *  - tablet: 2 (at most)
   *  - desktop: 3 (multi-column)
   *  - large: 4 (multi-column)
   */
  columnCount: number;
  /**
   * Nav mode for the active breakpoint:
   *  - "collapsible" on mobile/tablet (incl. sub-320) — nav lives behind a menu control (Requirement 5.2)
   *  - "persistent" on desktop/large — sidebar is always visible (Requirement 5.1)
   */
  navMode: NavMode;
  /**
   * Maximum content-region width in CSS px when capped (1440 at Large_Desktop,
   * Requirement 4.3); null when the content region is uncapped.
   */
  contentMaxWidth: number | null;
  /**
   * True only for sub-320 widths, signalling that horizontal page scroll is
   * permitted (Requirement 4.8). False for every supported width (>= 320px)
   * where horizontal scroll is forbidden (Requirement 4.4).
   */
  allowHorizontalScroll: boolean;
  /**
   * Convenience flag: true when {@link navMode} is "collapsible" (mobile or
   * tablet, Requirement 5.2). False when a persistent sidebar is shown
   * (desktop or large, Requirement 5.1).
   */
  isNavCollapsible: boolean;
  /**
   * True when metric charts must be arranged in a single column (Mobile band,
   * Requirement 4.5). False for tablet/desktop/large where charts may flow
   * multi-column.
   */
  chartsSingleColumn: boolean;
}

/**
 * Breakpoint threshold constants kept in one place so the design's breakpoint
 * table, the matchMedia queries below, and the classifier never drift.
 */
export const BREAKPOINT_THRESHOLDS = {
  /** Widths below this value permit horizontal scroll (Requirement 4.8). */
  subMobile: 320,
  /** Mobile -> Tablet threshold. */
  tablet: 640,
  /** Tablet -> Desktop threshold; persistent sidebar engages here (Requirement 5.1). */
  desktop: 1024,
  /** Desktop -> Large_Desktop threshold; content region cap engages here (Requirement 4.3). */
  large: 1440
} as const;

/**
 * Pure layout classifier. Maps a viewport width (in CSS px) to its Breakpoint
 * and the associated layout descriptor per the design's breakpoint table:
 *
 *   width <  320   : mobile,  1 col, collapsible nav, horizontal-scroll permitted (Req 4.8)
 *   320 <= w < 640 : mobile,  1 col, collapsible nav, no horizontal-scroll        (Req 4.1)
 *   640 <= w <1024 : tablet,  2 cols at most, collapsible nav                     (Req 4.2, 5.2)
 *  1024 <= w <1440 : desktop, multi cols, persistent sidebar                      (Req 5.1)
 *  1440 <= w       : large,   multi cols, persistent sidebar, content capped 1440 centered (Req 4.3)
 *
 * Non-finite or negative widths collapse to the sub-320 mobile band so callers
 * never see undefined behavior at the edges.
 */
export function classifyWidth(width: number): LayoutDescriptor {
  const w = Number.isFinite(width) && width > 0 ? width : 0;

  if (w < BREAKPOINT_THRESHOLDS.subMobile) {
    return {
      breakpoint: "mobile",
      columnCount: 1,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: true,
      isNavCollapsible: true,
      chartsSingleColumn: true
    };
  }

  if (w < BREAKPOINT_THRESHOLDS.tablet) {
    return {
      breakpoint: "mobile",
      columnCount: 1,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: true,
      chartsSingleColumn: true
    };
  }

  if (w < BREAKPOINT_THRESHOLDS.desktop) {
    return {
      breakpoint: "tablet",
      columnCount: 2,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: true,
      chartsSingleColumn: false
    };
  }

  if (w < BREAKPOINT_THRESHOLDS.large) {
    return {
      breakpoint: "desktop",
      columnCount: 3,
      navMode: "persistent",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: false,
      chartsSingleColumn: false
    };
  }

  return {
    breakpoint: "large",
    columnCount: 4,
    navMode: "persistent",
    contentMaxWidth: 1440,
    allowHorizontalScroll: false,
    isNavCollapsible: false,
    chartsSingleColumn: false
  };
}

/**
 * Default LayoutDescriptor when no DOM is available (SSR, tests without
 * `window`, or environments lacking `matchMedia`). Desktop is the safest
 * baseline: it renders the persistent sidebar with no horizontal scroll,
 * matching the dominant operations-console use case.
 */
const SSR_DEFAULT_DESCRIPTOR: LayoutDescriptor = classifyWidth(1280);

function hasMatchMedia(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function";
}

function readDescriptorFromWindow(): LayoutDescriptor {
  if (typeof window === "undefined") {
    return SSR_DEFAULT_DESCRIPTOR;
  }
  // window.innerWidth is the CSS viewport width media queries match against.
  return classifyWidth(window.innerWidth);
}

type MediaListener = (event: MediaQueryListEvent) => void;

function addMediaListener(list: MediaQueryList, listener: MediaListener): void {
  if (typeof list.addEventListener === "function") {
    list.addEventListener("change", listener);
    return;
  }
  // Safari < 14 and older browsers expose the legacy addListener API only.
  list.addListener(listener);
}

function removeMediaListener(list: MediaQueryList, listener: MediaListener): void {
  if (typeof list.removeEventListener === "function") {
    list.removeEventListener("change", listener);
    return;
  }
  list.removeListener(listener);
}

/**
 * Cache the descriptor so `useSyncExternalStore` receives a referentially
 * stable snapshot when the breakpoint band has not changed. Without this,
 * every re-render would produce a fresh object literal and React would treat
 * the snapshot as new, defeating the threshold-only re-render guarantee.
 */
let cachedDescriptor: LayoutDescriptor | null = null;

function getCachedDescriptor(): LayoutDescriptor {
  const next = readDescriptorFromWindow();
  if (
    cachedDescriptor !== null &&
    cachedDescriptor.breakpoint === next.breakpoint &&
    cachedDescriptor.allowHorizontalScroll === next.allowHorizontalScroll
  ) {
    return cachedDescriptor;
  }
  cachedDescriptor = next;
  return cachedDescriptor;
}

/**
 * Subscribe to the three threshold media queries (640 / 1024 / 1440). The same
 * listener fires for every threshold change, which is sufficient because
 * `useSyncExternalStore` only re-renders when the snapshot value changes.
 */
function subscribeBreakpoint(notify: () => void): () => void {
  if (!hasMatchMedia()) {
    return () => {
      /* no-op: no media queries to detach */
    };
  }

  const thresholds = [
    BREAKPOINT_THRESHOLDS.tablet,
    BREAKPOINT_THRESHOLDS.desktop,
    BREAKPOINT_THRESHOLDS.large
  ];

  const subscriptions = thresholds.map((minWidth) => {
    const list = window.matchMedia(`(min-width: ${minWidth}px)`);
    const listener: MediaListener = () => notify();
    addMediaListener(list, listener);
    return { list, listener };
  });

  return () => {
    for (const { list, listener } of subscriptions) {
      removeMediaListener(list, listener);
    }
  };
}

/**
 * React hook that reports the active LayoutDescriptor. Uses `window.matchMedia`
 * listeners at the 640 / 1024 / 1440 thresholds so re-renders only happen when
 * a defined threshold is crossed (Requirement 4.6). On SSR or environments
 * without `matchMedia`, returns a sensible desktop default.
 *
 * The returned object exposes `breakpoint` and `isNavCollapsible` (matching
 * the design's documented hook signature) alongside the rest of the layout
 * descriptor so consumers can render responsively without a second lookup.
 */
export function useBreakpoint(): LayoutDescriptor {
  return useSyncExternalStore(
    subscribeBreakpoint,
    getCachedDescriptor,
    () => SSR_DEFAULT_DESCRIPTOR
  );
}
