// Feature: ui-ux-responsive-redesign — task 13.2
// Integration tests for `PageContainer` / `ResponsiveGrid`.
//
// Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.6, 4.8
//
// Goal
// ----
// Drive the `<PageContainer>` and `<ResponsiveGrid>` components through
// simulated viewport widths spanning every breakpoint band and every
// threshold boundary (320 / 640 / 1024 / 1440), then assert the
// descriptor-driven data attributes the components expose for testability:
//
//   data-breakpoint               — current Breakpoint band
//   data-columns                  — effective column count after caps
//   data-content-max-width        — "1440" at Large_Desktop, "none" elsewhere
//   data-allow-horizontal-scroll  — "true" sub-320, "false" elsewhere
//
// The `useBreakpoint` hook is backed by `window.matchMedia` listeners at
// the 640 / 1024 / 1440 thresholds and reads the current width from
// `window.innerWidth`. These tests stub both so the rendered output reflects
// the band under test without depending on jsdom's default 1024×768 viewport.
//
// These are integration tests (not property-based): parameterized via
// `test.each` for readability. The property-based per-band correctness
// proof for the underlying classifier lives in
// `frontend/src/hooks/__tests__/useBreakpoint.property.test.ts`.

import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PageContainer, ResponsiveGrid } from "../PageContainer";

// ---------------------------------------------------------------------------
// Viewport stubs
// ---------------------------------------------------------------------------

type MediaListener = (event: MediaQueryListEvent) => void;

/**
 * Minimal `MediaQueryList`-compatible object. jsdom ships `MediaQueryList`
 * as a real DOM interface, but only the subset below is consulted by
 * `useBreakpoint`'s subscription path, so a structural stub is sufficient.
 */
interface FakeMediaQueryList {
  matches: boolean;
  media: string;
  onchange: ((event: MediaQueryListEvent) => void) | null;
  addEventListener: (type: "change", listener: MediaListener) => void;
  removeEventListener: (type: "change", listener: MediaListener) => void;
  addListener: (listener: MediaListener) => void;
  removeListener: (listener: MediaListener) => void;
  dispatchEvent: (event: Event) => boolean;
}

/**
 * Build a `matchMedia` implementation that reports `matches = true` whenever
 * the supplied `width` satisfies the `(min-width: Npx)` query. Mirrors the
 * media queries `useBreakpoint` subscribes to (640 / 1024 / 1440).
 */
function createMatchMedia(width: number): (query: string) => FakeMediaQueryList {
  return (query: string): FakeMediaQueryList => {
    const match = /\(min-width:\s*(\d+)px\)/.exec(query);
    const matches = match !== null ? width >= Number(match[1]) : false;
    return {
      matches,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    };
  };
}

/**
 * Synchronise `window.innerWidth` and `window.matchMedia` to the supplied
 * width before render. `useBreakpoint` reads `innerWidth` to classify the
 * band and subscribes to `matchMedia` at the threshold queries, so both must
 * agree for the rendered descriptor to reflect the band under test.
 */
function setViewportWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  // Cast: the structural FakeMediaQueryList satisfies every property the
  // hook reads, but it's not nominally a `MediaQueryList` instance.
  window.matchMedia = createMatchMedia(width) as unknown as typeof window.matchMedia;
}

// Snapshot the original implementations so each test starts from a clean slate.
const originalInnerWidth = window.innerWidth;
const originalMatchMedia = window.matchMedia;

beforeEach(() => {
  // Tests must set their own width; reset to a deterministic baseline first
  // so a missing setViewportWidth() call fails loudly rather than silently
  // inheriting the previous test's band.
  setViewportWidth(1024);
});

afterEach(() => {
  cleanup();
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: originalInnerWidth,
  });
  window.matchMedia = originalMatchMedia;
});

// ---------------------------------------------------------------------------
// Expected per-width descriptors (mirrors the breakpoint table)
// ---------------------------------------------------------------------------

/**
 * Expected data-attribute values rendered by `<PageContainer>` (with no
 * caller-supplied `columns` cap) for a given viewport width. Encodes the
 * design's breakpoint table so the parameterized assertions below have a
 * single source of truth.
 */
interface ExpectedAttrs {
  breakpoint: "mobile" | "tablet" | "desktop" | "large";
  columns: number;
  contentMaxWidth: "1440" | "none";
  allowHorizontalScroll: "true" | "false";
}

const SUB_MOBILE: ExpectedAttrs = {
  breakpoint: "mobile",
  columns: 1,
  contentMaxWidth: "none",
  allowHorizontalScroll: "true",
};
const MOBILE: ExpectedAttrs = {
  breakpoint: "mobile",
  columns: 1,
  contentMaxWidth: "none",
  allowHorizontalScroll: "false",
};
const TABLET: ExpectedAttrs = {
  breakpoint: "tablet",
  columns: 2,
  contentMaxWidth: "none",
  allowHorizontalScroll: "false",
};
const DESKTOP: ExpectedAttrs = {
  breakpoint: "desktop",
  columns: 3,
  contentMaxWidth: "none",
  allowHorizontalScroll: "false",
};
const LARGE: ExpectedAttrs = {
  breakpoint: "large",
  columns: 4,
  contentMaxWidth: "1440",
  allowHorizontalScroll: "false",
};

/**
 * Representative widths covering every band, plus every just-below / on
 * threshold boundary required by Req 4.6.
 */
const WIDTH_CASES: ReadonlyArray<readonly [number, ExpectedAttrs]> = [
  // sub-320: horizontal scroll permitted (Req 4.8)
  [300, SUB_MOBILE],
  // mobile band (Req 4.1)
  [320, MOBILE],
  [500, MOBILE],
  [639, MOBILE],
  // tablet band (Req 4.2)
  [640, TABLET],
  [800, TABLET],
  [1023, TABLET],
  // desktop band
  [1024, DESKTOP],
  [1280, DESKTOP],
  [1439, DESKTOP],
  // large band — content cap engages (Req 4.3)
  [1440, LARGE],
  [1920, LARGE],
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Render a `<PageContainer>` carrying a stable `data-testid`, then return the
 * root element so callers can inspect its data attributes.
 */
function renderPageContainer(
  width: number,
  props?: { columns?: number }
): HTMLElement {
  setViewportWidth(width);
  const { getByTestId } = render(
    <PageContainer data-testid="container" columns={props?.columns}>
      <p>content</p>
    </PageContainer>
  );
  return getByTestId("container");
}

function renderResponsiveGrid(
  width: number,
  props?: { maxColumns?: number }
): HTMLElement {
  setViewportWidth(width);
  const { getByTestId } = render(
    <ResponsiveGrid data-testid="grid" maxColumns={props?.maxColumns}>
      <p>cell</p>
    </ResponsiveGrid>
  );
  return getByTestId("grid");
}

function assertAttrs(element: HTMLElement, expected: ExpectedAttrs): void {
  expect(element.getAttribute("data-breakpoint")).toBe(expected.breakpoint);
  expect(element.getAttribute("data-columns")).toBe(String(expected.columns));
  expect(element.getAttribute("data-content-max-width")).toBe(expected.contentMaxWidth);
  expect(element.getAttribute("data-allow-horizontal-scroll")).toBe(expected.allowHorizontalScroll);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PageContainer — descriptor-driven data attributes per band", () => {
  it.each(WIDTH_CASES)(
    "width=%i renders the expected per-band attributes",
    (width, expected) => {
      const container = renderPageContainer(width);
      assertAttrs(container, expected);
    }
  );
});

describe("PageContainer — stability within a band (Req 4.6)", () => {
  // Two interior widths per band: attributes must be byte-identical because
  // the descriptor only changes when a defined threshold is crossed.
  const PAIRS: ReadonlyArray<readonly [string, number, number, ExpectedAttrs]> = [
    ["mobile", 360, 600, MOBILE],
    ["tablet", 700, 900, TABLET],
    ["desktop", 1100, 1300, DESKTOP],
    ["large", 1500, 1800, LARGE],
  ];

  it.each(PAIRS)(
    "band %s: widths %i and %i yield identical descriptor attributes",
    (_band, w1, w2, expected) => {
      const a = renderPageContainer(w1);
      assertAttrs(a, expected);
      // Tear down between mounts so jsdom does not retain the previous root.
      cleanup();
      const b = renderPageContainer(w2);
      assertAttrs(b, expected);

      // Spot-check the per-attribute equality so a regression that changes
      // only one attribute (e.g. column count) still trips this test.
      expect(b.getAttribute("data-breakpoint")).toBe(a.getAttribute("data-breakpoint"));
      expect(b.getAttribute("data-columns")).toBe(a.getAttribute("data-columns"));
      expect(b.getAttribute("data-content-max-width")).toBe(
        a.getAttribute("data-content-max-width")
      );
      expect(b.getAttribute("data-allow-horizontal-scroll")).toBe(
        a.getAttribute("data-allow-horizontal-scroll")
      );
    }
  );
});

describe("PageContainer — threshold boundary flips (Req 4.6)", () => {
  // Pairs of adjacent widths that straddle each defined threshold. Exactly
  // one side must classify into the higher band.
  const BOUNDARIES: ReadonlyArray<readonly [number, ExpectedAttrs, number, ExpectedAttrs]> = [
    [639, MOBILE, 640, TABLET],
    [1023, TABLET, 1024, DESKTOP],
    [1439, DESKTOP, 1440, LARGE],
  ];

  it.each(BOUNDARIES)(
    "%i (%o) flips to %i (%o) across the threshold",
    (lo, expectedLo, hi, expectedHi) => {
      const below = renderPageContainer(lo);
      assertAttrs(below, expectedLo);
      cleanup();
      const above = renderPageContainer(hi);
      assertAttrs(above, expectedHi);

      // Sanity: at least one of the four attributes must differ across the
      // threshold — otherwise the classifier silently merged the two bands.
      const differingAttrs = (
        ["data-breakpoint", "data-columns", "data-content-max-width"] as const
      ).filter((name) => below.getAttribute(name) !== above.getAttribute(name));
      expect(differingAttrs.length).toBeGreaterThan(0);
    }
  );

  it("sub-320 → mobile flip (319 → 320) toggles allow-horizontal-scroll (Req 4.8 → 4.4)", () => {
    const below = renderPageContainer(319);
    assertAttrs(below, SUB_MOBILE);
    cleanup();
    const above = renderPageContainer(320);
    assertAttrs(above, MOBILE);

    // The defining flip across this threshold is horizontal-scroll permission;
    // every other attribute stays put (both bands are still single-column mobile).
    expect(below.getAttribute("data-allow-horizontal-scroll")).toBe("true");
    expect(above.getAttribute("data-allow-horizontal-scroll")).toBe("false");
    expect(below.getAttribute("data-breakpoint")).toBe(above.getAttribute("data-breakpoint"));
    expect(below.getAttribute("data-columns")).toBe(above.getAttribute("data-columns"));
  });
});

describe("PageContainer — caller-supplied `columns` cap", () => {
  // Caller asks for a cap of 2; descriptor's natural columnCount is 3 (desktop)
  // or 4 (large). The cap MUST take effect, so data-columns="2" in both cases.
  const CAP_CASES: ReadonlyArray<readonly [string, number, number]> = [
    ["desktop", 1280, 3],
    ["large", 1920, 4],
  ];

  it.each(CAP_CASES)(
    "%s (width=%i) caps data-columns to 2 instead of the natural %i",
    (_band, width, natural) => {
      // Sanity: without the cap, the natural column count is rendered.
      const uncapped = renderPageContainer(width);
      expect(uncapped.getAttribute("data-columns")).toBe(String(natural));
      cleanup();

      // With the cap, data-columns is min(cap, natural) = 2.
      const capped = renderPageContainer(width, { columns: 2 });
      expect(capped.getAttribute("data-columns")).toBe("2");
      // The breakpoint and content-cap attributes still reflect the band.
      expect(capped.getAttribute("data-breakpoint")).toBe(_band);
    }
  );

  it("a cap above the natural column count is ignored (min wins)", () => {
    // Tablet's natural columnCount is 2; a cap of 5 must not raise it.
    const el = renderPageContainer(800, { columns: 5 });
    expect(el.getAttribute("data-columns")).toBe("2");
  });
});

describe("PageContainer — horizontal scroll permission per band (Req 4.4, 4.8)", () => {
  it("data-allow-horizontal-scroll is \"true\" only at sub-320 widths", () => {
    const sub320 = renderPageContainer(300);
    expect(sub320.getAttribute("data-allow-horizontal-scroll")).toBe("true");
  });

  it.each(WIDTH_CASES.filter(([, attrs]) => attrs !== SUB_MOBILE))(
    "width=%i is supported (>= 320px) and forbids horizontal page scroll",
    (width) => {
      const el = renderPageContainer(width);
      expect(el.getAttribute("data-allow-horizontal-scroll")).toBe("false");
    }
  );
});

describe("ResponsiveGrid — descriptor-driven data attributes", () => {
  // ResponsiveGrid mirrors `data-breakpoint` and `data-columns` from the
  // descriptor (it doesn't render a content cap, since it's a child concept).
  const GRID_CASES: ReadonlyArray<readonly [number, ExpectedAttrs["breakpoint"], number]> = [
    [300, "mobile", 1],
    [500, "mobile", 1],
    [800, "tablet", 2],
    [1280, "desktop", 3],
    [1920, "large", 4],
  ];

  it.each(GRID_CASES)(
    "width=%i renders data-breakpoint=%s and data-columns=%i",
    (width, breakpoint, columns) => {
      const grid = renderResponsiveGrid(width);
      expect(grid.getAttribute("data-breakpoint")).toBe(breakpoint);
      expect(grid.getAttribute("data-columns")).toBe(String(columns));
    }
  );

  it.each([
    ["desktop", 1280, 3],
    ["large", 1920, 4],
  ] as const)(
    "%s (width=%i) caps data-columns via maxColumns instead of the natural %i",
    (_band, width, natural) => {
      const uncapped = renderResponsiveGrid(width);
      expect(uncapped.getAttribute("data-columns")).toBe(String(natural));
      cleanup();

      const capped = renderResponsiveGrid(width, { maxColumns: 2 });
      expect(capped.getAttribute("data-columns")).toBe("2");
    }
  );
});
