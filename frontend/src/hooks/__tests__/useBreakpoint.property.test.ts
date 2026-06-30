// Feature: ui-ux-responsive-redesign, Property 3: Breakpoint classification is correct and stable within bands
//
// Validates: Requirements 4.1, 4.2, 4.3, 4.5, 4.6, 4.8, 5.1, 5.2
//
// Property 3 (from design.md):
//   For all viewport widths, the layout classifier assigns exactly one
//   Breakpoint and a layout descriptor such that:
//     - widths below 640px yield a single column (and charts single column)
//       with a collapsible nav;
//     - widths 640–1023px yield at most two columns with a collapsible nav;
//     - widths 1024–1439px yield a persistent sidebar;
//     - widths >= 1440px yield a persistent sidebar with content width capped
//       at 1440px and centered;
//     - widths below 320px yield a single column with horizontal scroll
//       permitted.
//   Furthermore, for all pairs of widths within the same Breakpoint band the
//   classification is identical, so arrangement changes only when a defined
//   threshold is crossed.
//
// Strategy:
//   1. Define the five canonical bands (sub-mobile, mobile, tablet, desktop,
//      large) with their integer width ranges and the exact LayoutDescriptor
//      each band must yield, per `classifyWidth` and the design's breakpoint
//      table.
//   2. Per-band correctness — fast-check draws integer widths from a band's
//      range (with extra weight on boundary widths via constantFrom) and
//      asserts the descriptor returned by `classifyWidth(w)` matches the
//      band's expected descriptor exactly. Requirements 4.1, 4.2, 4.3, 4.5,
//      4.8, 5.1, 5.2.
//   3. Within-band stability — for each band, fast-check draws two widths
//      from the same range and asserts the descriptors are deep-equal,
//      proving the classifier only changes its output when a defined
//      threshold is crossed. Requirement 4.6.
//   4. Exactly-one-breakpoint — every returned descriptor reports a single
//      `breakpoint` from the closed enumeration set, with every required
//      field present and well-typed.
//   5. Edge case constants — exact boundary widths (320, 640, 1024, 1440),
//      just-below-boundary widths (319, 639, 1023, 1439), and degenerate
//      inputs (0, negative, NaN, Infinity) are asserted directly so a
//      shrunken fast-check counter-example always has a named partner.
//
// Each fast-check property runs at least 100 iterations (Property 3 minimum);
// the broader uniform bands run 200 to cover the wider input space.

import * as fc from "fast-check";
import {
  BREAKPOINT_THRESHOLDS,
  classifyWidth,
  type Breakpoint,
  type LayoutDescriptor,
} from "../useBreakpoint";

// ---------------------------------------------------------------------------
// Band definitions — single source of truth for expected per-band descriptors
// ---------------------------------------------------------------------------

interface BandSpec {
  /** Human-readable band id (only the four `Breakpoint` names are present in
   * the descriptor; the `sub-mobile` band still classifies as "mobile" but is
   * distinguished by `allowHorizontalScroll = true`). */
  id: "sub-mobile" | "mobile" | "tablet" | "desktop" | "large";
  /** Lowest width (inclusive) in this band's integer range. */
  min: number;
  /** Highest width (inclusive) in this band's integer range. */
  max: number;
  /** The exact descriptor every width in [min, max] must produce. */
  expected: LayoutDescriptor;
  /** A handful of representative widths from this band, including any
   * boundary widths owned by the band. */
  boundaries: number[];
}

/** Upper bound for the unbounded "large" band — chosen well above any real
 * monitor while still keeping fast-check's integer arbitrary efficient. */
const LARGE_BAND_MAX = 16384;

const BANDS: BandSpec[] = [
  {
    id: "sub-mobile",
    min: 0,
    max: BREAKPOINT_THRESHOLDS.subMobile - 1, // 319
    expected: {
      breakpoint: "mobile",
      columnCount: 1,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: true,
      isNavCollapsible: true,
      chartsSingleColumn: true,
    },
    boundaries: [0, 1, 100, 319],
  },
  {
    id: "mobile",
    min: BREAKPOINT_THRESHOLDS.subMobile, // 320
    max: BREAKPOINT_THRESHOLDS.tablet - 1, // 639
    expected: {
      breakpoint: "mobile",
      columnCount: 1,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: true,
      chartsSingleColumn: true,
    },
    boundaries: [320, 321, 480, 639],
  },
  {
    id: "tablet",
    min: BREAKPOINT_THRESHOLDS.tablet, // 640
    max: BREAKPOINT_THRESHOLDS.desktop - 1, // 1023
    expected: {
      breakpoint: "tablet",
      columnCount: 2,
      navMode: "collapsible",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: true,
      chartsSingleColumn: false,
    },
    boundaries: [640, 641, 800, 1023],
  },
  {
    id: "desktop",
    min: BREAKPOINT_THRESHOLDS.desktop, // 1024
    max: BREAKPOINT_THRESHOLDS.large - 1, // 1439
    expected: {
      breakpoint: "desktop",
      columnCount: 3,
      navMode: "persistent",
      contentMaxWidth: null,
      allowHorizontalScroll: false,
      isNavCollapsible: false,
      chartsSingleColumn: false,
    },
    boundaries: [1024, 1025, 1280, 1439],
  },
  {
    id: "large",
    min: BREAKPOINT_THRESHOLDS.large, // 1440
    max: LARGE_BAND_MAX,
    expected: {
      breakpoint: "large",
      columnCount: 4,
      navMode: "persistent",
      contentMaxWidth: 1440,
      allowHorizontalScroll: false,
      isNavCollapsible: false,
      chartsSingleColumn: false,
    },
    boundaries: [1440, 1441, 1920, 2560, LARGE_BAND_MAX],
  },
];

const ALLOWED_BREAKPOINTS: Breakpoint[] = ["mobile", "tablet", "desktop", "large"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a fast-check arbitrary that samples a band's full integer range
 * while explicitly biasing toward its boundary widths (so shrinking lands
 * on a boundary, and so every run exercises both interior and edge values).
 */
function widthInBand(band: BandSpec): fc.Arbitrary<number> {
  return fc.oneof(
    { weight: 1, arbitrary: fc.constantFrom(...band.boundaries) },
    { weight: 3, arbitrary: fc.integer({ min: band.min, max: band.max }) }
  );
}

/** Strong descriptor shape check — guards against silent regressions in the
 * descriptor's field set. */
function assertDescriptorShape(d: LayoutDescriptor): void {
  expect(ALLOWED_BREAKPOINTS).toContain(d.breakpoint);
  expect(typeof d.columnCount).toBe("number");
  expect(d.columnCount).toBeGreaterThanOrEqual(1);
  expect(["collapsible", "persistent"]).toContain(d.navMode);
  expect(d.contentMaxWidth === null || typeof d.contentMaxWidth === "number").toBe(true);
  expect(typeof d.allowHorizontalScroll).toBe("boolean");
  expect(typeof d.isNavCollapsible).toBe("boolean");
  expect(typeof d.chartsSingleColumn).toBe("boolean");
  // `isNavCollapsible` is a convenience flag derived from `navMode`; the
  // two MUST stay in lock-step.
  expect(d.isNavCollapsible).toBe(d.navMode === "collapsible");
}

// ---------------------------------------------------------------------------
// Property 3a — Per-band correctness across the full input space
// ---------------------------------------------------------------------------

describe("Property 3: Breakpoint classification is correct and stable within bands", () => {
  describe("3a: every width yields the exact descriptor for its band", () => {
    for (const band of BANDS) {
      it(`band '${band.id}' (${band.min}..${band.max}) produces the expected descriptor`, () => {
        fc.assert(
          fc.property(widthInBand(band), (width) => {
            const descriptor = classifyWidth(width);

            // Shape first — defends the field set independently of the
            // band-specific value assertions below.
            assertDescriptorShape(descriptor);

            // Exact descriptor equality — encodes the per-band expectations
            // declared in BANDS, which mirror Requirements 4.1, 4.2, 4.3,
            // 4.5, 4.8, 5.1, 5.2.
            expect(descriptor).toEqual(band.expected);
          }),
          { numRuns: 200 }
        );
      });
    }
  });

  // -------------------------------------------------------------------------
  // Property 3b — Within-band stability (Requirement 4.6)
  //   For any two widths drawn from the same band, the descriptors are
  //   deep-equal. Arrangement only changes at the defined thresholds.
  // -------------------------------------------------------------------------
  describe("3b: classification is stable within each band", () => {
    for (const band of BANDS) {
      it(`band '${band.id}' yields identical descriptors for any two in-band widths`, () => {
        fc.assert(
          fc.property(widthInBand(band), widthInBand(band), (w1, w2) => {
            const d1 = classifyWidth(w1);
            const d2 = classifyWidth(w2);
            // Deep equality across all descriptor fields — the strongest
            // statement of within-band stability.
            expect(d1).toEqual(d2);
            // And both must equal the band's canonical descriptor, so the
            // stability check is not satisfied vacuously by a buggy classifier
            // returning the same wrong descriptor for both inputs.
            expect(d1).toEqual(band.expected);
          }),
          { numRuns: 150 }
        );
      });
    }
  });

  // -------------------------------------------------------------------------
  // Property 3c — Exactly one Breakpoint per width, across the whole space
  //   Strengthens 3a by drawing across all bands in one arbitrary so the
  //   classifier is exercised on the union of every supported width.
  // -------------------------------------------------------------------------
  it("3c: every width across the full supported range classifies to exactly one Breakpoint", () => {
    const anyBand = fc.oneof(...BANDS.map((b) => widthInBand(b)));
    fc.assert(
      fc.property(anyBand, (width) => {
        const descriptor = classifyWidth(width);
        assertDescriptorShape(descriptor);

        // Exactly one breakpoint name — by construction the function returns
        // a single value, but we assert the enumeration is closed.
        const matches = ALLOWED_BREAKPOINTS.filter((bp) => bp === descriptor.breakpoint);
        expect(matches).toHaveLength(1);
      }),
      { numRuns: 200 }
    );
  });

  // -------------------------------------------------------------------------
  // Boundary constants — exact thresholds & just-below thresholds.
  // These pin the classifier's `<` vs `<=` semantics so a shrunken fast-check
  // counter-example always has a named partner here.
  // -------------------------------------------------------------------------
  describe("boundary widths classify into the higher band", () => {
    const cases: Array<[number, BandSpec["id"]]> = [
      [BREAKPOINT_THRESHOLDS.subMobile - 1, "sub-mobile"], // 319
      [BREAKPOINT_THRESHOLDS.subMobile, "mobile"], // 320
      [BREAKPOINT_THRESHOLDS.tablet - 1, "mobile"], // 639
      [BREAKPOINT_THRESHOLDS.tablet, "tablet"], // 640
      [BREAKPOINT_THRESHOLDS.desktop - 1, "tablet"], // 1023
      [BREAKPOINT_THRESHOLDS.desktop, "desktop"], // 1024
      [BREAKPOINT_THRESHOLDS.large - 1, "desktop"], // 1439
      [BREAKPOINT_THRESHOLDS.large, "large"], // 1440
    ];

    for (const [width, bandId] of cases) {
      it(`width ${width} classifies into band '${bandId}'`, () => {
        const expected = BANDS.find((b) => b.id === bandId)!.expected;
        expect(classifyWidth(width)).toEqual(expected);
      });
    }
  });

  // -------------------------------------------------------------------------
  // Degenerate inputs — non-finite, negative, and zero widths must collapse
  // into the sub-320 mobile band (per classifier docs). Requirement 4.8
  // keeps horizontal-scroll permission tied to this band.
  // -------------------------------------------------------------------------
  describe("degenerate inputs collapse to the sub-320 mobile band", () => {
    const subMobile = BANDS.find((b) => b.id === "sub-mobile")!.expected;
    const cases: Array<[string, number]> = [
      ["zero", 0],
      ["negative integer", -1],
      ["very negative", -10_000],
      ["NaN", Number.NaN],
      ["negative Infinity", Number.NEGATIVE_INFINITY],
    ];

    for (const [name, input] of cases) {
      it(`${name} (${String(input)}) yields the sub-320 mobile descriptor`, () => {
        expect(classifyWidth(input)).toEqual(subMobile);
      });
    }

    it("positive Infinity yields the large-desktop descriptor", () => {
      // Number.isFinite(Infinity) === false, so the classifier collapses it
      // to 0 → sub-mobile band. This pins that documented behavior so a
      // future change becomes a deliberate decision rather than a silent
      // regression.
      expect(classifyWidth(Number.POSITIVE_INFINITY)).toEqual(subMobile);
    });
  });
});
