// Feature: ui-ux-responsive-redesign, Property 7: Interactive controls meet the minimum touch-target size
//
// Validates: Requirements 6.5
//
// Property 7 (from design.md):
//   For all interactive UI component variants (buttons, inputs, selects,
//   textareas, the menu control, and nav links), the rendered control exposes
//   a hit area of at least 44px by 44px.
//
// Wave-4 scope:
//   This test covers the primitive variants implemented in task 9 of the
//   tasks.md plan: Button (primary, secondary, ghost), TextInput, Select,
//   Textarea. The NavigationShell menu control and nav links arrive in
//   task 12.1; once that lands a follow-up extension will fold them into
//   the variant table below. Property 7's scope is universally quantified
//   over "the rendered control", so as long as every implemented variant is
//   in the table, the property holds for the implemented surface.
//
// Why source-driven assertion vs. getComputedStyle?
//   jsdom does not implement real layout, so getBoundingClientRect /
//   offsetWidth always return 0. The design strategy explicitly accepts
//   "assert the className/data attribute and a direct style assertion": we
//   read the primitive CSS sources at test time, resolve the var(--token)
//   and calc(...) expressions against tokens.css, and assert the resulting
//   min-width and min-height pixel values are >= 44. Each fast-check
//   iteration also renders the primitive with an arbitrary unicode label
//   and verifies the rendered DOM element exposes the class identity that
//   the CSS rule targets — so a regression that removes the class binding
//   from the component, the rule from the stylesheet, or the token from
//   tokens.css, all break the property.

import { readFileSync } from "fs";
import { resolve } from "path";

import * as fc from "fast-check";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Button } from "../Button";
import buttonStyles from "../Button.module.css";
import { Select, Textarea, TextInput } from "../Field";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** WCAG 2.5.5 minimum hit area, in CSS pixels. */
const MIN_TOUCH_TARGET_PX = 44;

/**
 * Default browser root font size; tokens.css authors the scale in `rem`
 * (e.g. `--size-touch-target-min: 2.75rem`) which resolves against this.
 * Keep this in lock-step with the project's <html> font-size — the design
 * does not override it.
 */
const ROOT_FONT_SIZE_PX = 16;

// ---------------------------------------------------------------------------
// CSS source loading
// ---------------------------------------------------------------------------

const STYLES_DIR = resolve(__dirname, "../../../styles");
const UI_DIR = resolve(__dirname, "..");

const tokensCss = readFileSync(resolve(STYLES_DIR, "tokens.css"), "utf8");
const buttonCss = readFileSync(resolve(UI_DIR, "Button.module.css"), "utf8");
const fieldCss = readFileSync(resolve(UI_DIR, "Field.css"), "utf8");

// ---------------------------------------------------------------------------
// CSS token + length resolver
// ---------------------------------------------------------------------------

/** Extract `--name: value;` pairs from the :root block of tokens.css. */
function parseRootTokens(css: string): Map<string, string> {
  const tokens = new Map<string, string>();
  const rootMatch = /:root\s*\{([\s\S]*?)\n\}/.exec(css);
  if (!rootMatch) {
    throw new Error("touchTargetSize: :root block not found in tokens.css");
  }
  const declRe = /(--[\w-]+)\s*:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = declRe.exec(rootMatch[1])) !== null) {
    tokens.set(m[1], m[2].trim());
  }
  return tokens;
}

const TOKENS = parseRootTokens(tokensCss);

/**
 * Pull the LAST declaration matching `prop` from any rule whose comma-
 * separated selector list contains the exact `selector` (e.g. `.button`,
 * `.field__textarea`). "Last wins" mirrors the CSS cascade for same-
 * specificity rules, so the textarea's override of `min-height` (88px)
 * shadows the shared input rule's 44px floor.
 */
function readCssRuleValue(
  css: string,
  selector: string,
  prop: string
): string | null {
  // Strip comments before scanning so commented-out rules never match.
  const cleaned = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const ruleRe = /([^{}@]+)\{([^{}]*)\}/g;
  const escapedProp = prop.replace(/-/g, "\\-");
  let lastValue: string | null = null;
  let m: RegExpExecArray | null;
  while ((m = ruleRe.exec(cleaned)) !== null) {
    const selectorList = m[1].split(",").map((s) => s.trim());
    if (!selectorList.includes(selector)) continue;
    const declRe = new RegExp(
      `(?:^|[\\s;])${escapedProp}\\s*:\\s*([^;]+);`,
      "g"
    );
    let dm: RegExpExecArray | null;
    while ((dm = declRe.exec(m[2])) !== null) {
      lastValue = dm[1].trim();
    }
  }
  return lastValue;
}

/**
 * Recursively resolve all `var(--token[, fallback])` references against the
 * token map; throws if any token is unresolved (a real bug — the CSS would
 * silently fall back to `initial` in the browser).
 */
function resolveVars(expr: string): string {
  let current = expr;
  for (let safety = 0; safety < 32; safety++) {
    const next = current.replace(
      /var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)/g,
      (_match, name, fallback) => {
        const value = TOKENS.get(name);
        if (value !== undefined) return value;
        if (fallback !== undefined) return String(fallback).trim();
        throw new Error(`touchTargetSize: unresolved CSS variable ${name}`);
      }
    );
    if (next === current) return current;
    current = next;
  }
  throw new Error(`touchTargetSize: var() resolution exceeded depth in ${expr}`);
}

/** Convert a numeric length token (e.g. "2.75rem", "44px") to CSS pixels. */
function lengthTokenToPx(token: string): number {
  const trimmed = token.trim();
  const remMatch = /^(-?\d+(?:\.\d+)?)\s*rem$/.exec(trimmed);
  if (remMatch) return parseFloat(remMatch[1]) * ROOT_FONT_SIZE_PX;
  const pxMatch = /^(-?\d+(?:\.\d+)?)\s*px$/.exec(trimmed);
  if (pxMatch) return parseFloat(pxMatch[1]);
  const bareNumber = /^(-?\d+(?:\.\d+)?)$/.exec(trimmed);
  if (bareNumber) return parseFloat(bareNumber[1]);
  throw new Error(`touchTargetSize: unsupported length unit in "${token}"`);
}

/**
 * Evaluate a fully token-resolved arithmetic expression that contains only
 * `rem` / `px` lengths combined with `+ - * /` and parentheses. The expression
 * is validated to be alphanumeric/operator-only before being passed to
 * `Function` to keep eval-injection risk contained — but every input comes
 * from the in-repo CSS files anyway.
 */
function evaluateArithmetic(expr: string): number {
  // Replace every length literal with its pixel value, then evaluate.
  const pxExpr = expr.replace(
    /(-?\d+(?:\.\d+)?)\s*(rem|px)/g,
    (_match, num, unit) => {
      const value =
        unit === "rem"
          ? parseFloat(num) * ROOT_FONT_SIZE_PX
          : parseFloat(num);
      return value.toString();
    }
  );
  if (!/^[\d+\-*/().\s]+$/.test(pxExpr)) {
    throw new Error(
      `touchTargetSize: refusing to evaluate non-arithmetic expression "${pxExpr}"`
    );
  }
  // eslint-disable-next-line no-new-func
  const fn = new Function(`"use strict"; return (${pxExpr});`);
  const result = fn();
  if (typeof result !== "number" || !Number.isFinite(result)) {
    throw new Error(`touchTargetSize: expression "${expr}" did not yield a finite number`);
  }
  return result;
}

/**
 * Fully resolve a CSS length expression (with `var()` and `calc()`) to a
 * pixel number.
 *
 * Strategy: substitute every var() against the token map first, then drop
 * the `calc` keyword (the arithmetic evaluator handles parentheses natively,
 * so `calc((2.5rem + 0.25rem) * 2)` becomes `((2.5rem + 0.25rem) * 2)` — a
 * valid arithmetic expression that evaluates to 88px).
 */
function resolveLengthToPx(expression: string): number {
  // Substitute every var() reference; calc() may contain nested vars.
  let resolved = resolveVars(expression);

  // Strip every `calc` wrapper; the surrounding parens remain and are
  // evaluated as ordinary grouping by `evaluateArithmetic`.
  resolved = resolved.replace(/\bcalc\b/g, "").trim();

  // If any arithmetic operator or grouping remains, evaluate it; otherwise
  // the value is already a single length token (e.g. "2.75rem").
  if (/[+\-*/()]/.test(resolved)) {
    return evaluateArithmetic(resolved);
  }
  return lengthTokenToPx(resolved);
}

// ---------------------------------------------------------------------------
// Variant table
// ---------------------------------------------------------------------------

type ButtonVariantId = "button-primary" | "button-secondary" | "button-ghost";
type FieldVariantId = "text-input" | "select" | "textarea";
type VariantId = ButtonVariantId | FieldVariantId;

interface VariantSpec {
  id: VariantId;
  /** CSS source the size rule lives in. */
  cssSource: string;
  /** Base CSS selector whose min-width / min-height own the touch target. */
  selector: string;
  /** Expected rendered DOM tag for the actual interactive control. */
  controlTagName: "BUTTON" | "INPUT" | "SELECT" | "TEXTAREA";
  /**
   * A class identity that the rendered control's className attribute MUST
   * contain. For CSS Modules (Button) this is the hashed class produced by
   * the Vite/Vitest CSS pipeline; for plain CSS (Field) it is the literal
   * class name authored in Field.css.
   */
  expectedClassIdentity: string;
  /** Render the variant with the supplied label string. */
  render(label: string): JSX.Element;
}

const VARIANTS: VariantSpec[] = [
  {
    id: "button-primary",
    cssSource: buttonCss,
    selector: ".button",
    controlTagName: "BUTTON",
    expectedClassIdentity: buttonStyles.button,
    render: (label) => <Button variant="primary">{label}</Button>,
  },
  {
    id: "button-secondary",
    cssSource: buttonCss,
    selector: ".button",
    controlTagName: "BUTTON",
    expectedClassIdentity: buttonStyles.button,
    render: (label) => <Button variant="secondary">{label}</Button>,
  },
  {
    id: "button-ghost",
    cssSource: buttonCss,
    selector: ".button",
    controlTagName: "BUTTON",
    expectedClassIdentity: buttonStyles.button,
    render: (label) => <Button variant="ghost">{label}</Button>,
  },
  {
    id: "text-input",
    cssSource: fieldCss,
    selector: ".field__input",
    controlTagName: "INPUT",
    expectedClassIdentity: "field__input",
    render: (label) => (
      <TextInput
        label={label}
        value=""
        onChange={() => {
          /* no-op */
        }}
      />
    ),
  },
  {
    id: "select",
    cssSource: fieldCss,
    selector: ".field__select",
    controlTagName: "SELECT",
    expectedClassIdentity: "field__select",
    render: (label) => (
      <Select
        label={label}
        value=""
        onChange={() => {
          /* no-op */
        }}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />
    ),
  },
  {
    id: "textarea",
    cssSource: fieldCss,
    selector: ".field__textarea",
    controlTagName: "TEXTAREA",
    expectedClassIdentity: "field__textarea",
    render: (label) => (
      <Textarea
        label={label}
        value=""
        onChange={() => {
          /* no-op */
        }}
      />
    ),
  },
];

/** Pre-compute the effective min-width / min-height per variant (CSS source
 *  is static, so resolving once is far cheaper than resolving 100+ times). */
const EFFECTIVE_MIN_PX_BY_VARIANT: Record<
  VariantId,
  { minWidthPx: number; minHeightPx: number }
> = (() => {
  const out = {} as Record<VariantId, { minWidthPx: number; minHeightPx: number }>;
  for (const variant of VARIANTS) {
    const minWidthRaw = readCssRuleValue(variant.cssSource, variant.selector, "min-width");
    const minHeightRaw = readCssRuleValue(variant.cssSource, variant.selector, "min-height");
    if (minWidthRaw === null) {
      throw new Error(
        `touchTargetSize: no min-width rule for ${variant.selector} (variant ${variant.id})`
      );
    }
    if (minHeightRaw === null) {
      throw new Error(
        `touchTargetSize: no min-height rule for ${variant.selector} (variant ${variant.id})`
      );
    }
    out[variant.id] = {
      minWidthPx: resolveLengthToPx(minWidthRaw),
      minHeightPx: resolveLengthToPx(minHeightRaw),
    };
  }
  return out;
})();

// ---------------------------------------------------------------------------
// Property: 6 variants × arbitrary unicode labels, all >= 44x44
// ---------------------------------------------------------------------------

describe("Property 7: Interactive controls meet the minimum touch-target size (Requirement 6.5)", () => {
  afterEach(() => {
    cleanup();
  });

  // Fixed-list arbitrary so the shrinker can name the failing variant.
  const arbVariant = fc.constantFrom(...VARIANTS);
  // Allow empty strings (legitimate label/children) plus full unicode so the
  // generator covers degenerate and exotic text. `unicodeString` excludes
  // lone surrogates and other invalid code points that React would reject.
  const arbLabel = fc.unicodeString({ minLength: 0, maxLength: 32 });

  it("renders every implemented primitive with an effective hit area >= 44 x 44 px", () => {
    fc.assert(
      fc.property(arbVariant, arbLabel, (variant, label) => {
        // Always start each iteration with a clean DOM so prior renders do
        // not leak `<input>` / `<button>` elements into our queries.
        cleanup();
        const { container } = render(variant.render(label));

        // 1. The variant produces a control of the expected DOM type.
        const control = container.querySelector(
          variant.controlTagName.toLowerCase()
        ) as HTMLElement | null;
        expect(control).not.toBeNull();
        expect(control!.tagName).toBe(variant.controlTagName);

        // 2. The rendered control carries the class identity the size rule
        //    targets. If `expectedClassIdentity` is empty (which would mean
        //    the CSS Modules pipeline failed to produce a class), this assertion
        //    catches the regression rather than silently passing.
        expect(variant.expectedClassIdentity).toBeTruthy();
        const classList = control!.className.split(/\s+/).filter(Boolean);
        expect(classList).toContain(variant.expectedClassIdentity);

        // 3. The token-resolved min-width and min-height for that class
        //    each meet the 44px floor. This is the actual size constraint.
        const { minWidthPx, minHeightPx } =
          EFFECTIVE_MIN_PX_BY_VARIANT[variant.id];
        expect(minWidthPx).toBeGreaterThanOrEqual(MIN_TOUCH_TARGET_PX);
        expect(minHeightPx).toBeGreaterThanOrEqual(MIN_TOUCH_TARGET_PX);
      }),
      { numRuns: 120, verbose: false }
    );
  });
});
