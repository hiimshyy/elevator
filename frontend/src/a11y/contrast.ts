// =============================================================================
// WCAG 2.1 contrast utility + token-pairing map — Elevator PDM Operations Console
// Requirements: 6.1, 6.2, 6.4, 8.8
//
// This module exposes two surfaces used together by the palette-contrast
// property test (task 10.2) and by any future runtime / audit tooling:
//
//   1. Pure colour utilities — `parseColor`, `composite`, `relativeLuminance`,
//      `contrastRatio` — implementing the WCAG 2.1 relative-luminance formula
//      and standard "over" alpha compositing.
//
//   2. A typed enumeration of the actual foreground / background token pairings
//      that appear together in the application's component CSS — split by
//      category (normal-text, large-text, status-graphical, focus-indicator) —
//      together with helpers (`resolveToken`, `resolveBackgroundLayers`,
//      `contrastForPairing`) that walk those pairings against the live token
//      values parsed from `styles/tokens.css`.
//
// The split keeps the math pure (so the property test can target it without a
// DOM) while keeping the canonical token values in `tokens.css` as the single
// source of truth (parsed at module load via Vite's `?raw` import, matching
// the existing pattern used by the token-resolution test suite).
// =============================================================================

import tokensCss from "../styles/tokens.css?raw";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Active theme name; matches `ThemeProvider.ThemeName`. */
export type ThemeName = "light" | "dark";

/**
 * RGB colour with red/green/blue channels in `[0, 255]` and an alpha channel
 * in `[0, 1]`. All colour values flowing through the contrast pipeline use
 * this shape so alpha compositing and luminance can both be expressed
 * uniformly.
 */
export interface RGBAColor {
  /** Red channel, 0 – 255 inclusive. */
  r: number;
  /** Green channel, 0 – 255 inclusive. */
  g: number;
  /** Blue channel, 0 – 255 inclusive. */
  b: number;
  /** Alpha channel, 0 (fully transparent) – 1 (fully opaque). */
  a: number;
}

/** Categories of contrast pairing tracked by the design (Property 6). */
export type PairingCategory =
  | "normal-text"
  | "large-text"
  | "status-graphical"
  | "focus-indicator";

/**
 * WCAG AA contrast threshold for a category:
 *  - 4.5 for normal-size text (Req 6.1)
 *  - 3   for large-size text, status graphical elements, and focus indicators
 *        (Req 6.2, 6.4)
 */
export type ContrastThreshold = 4.5 | 3;

/**
 * A single foreground / background pairing that the application renders
 * together. Backgrounds are expressed as an ordered list of CSS custom-property
 * names from the layer immediately under the foreground down to an opaque
 * base layer — so translucent surfaces like `--color-surface` and the status
 * background tokens can be composited in the order they appear in the DOM.
 */
export interface TokenPairing {
  /** Stable identifier for the pairing (used by the property test report). */
  id: string;
  /** Which WCAG category this pairing falls into. */
  category: PairingCategory;
  /** Foreground token name, e.g. `"--color-text"`. */
  foreground: string;
  /**
   * Background stack ordered top-to-bottom. The deepest entry must resolve to
   * an opaque colour in every theme so the composite chain has a well-defined
   * starting point.
   */
  backgroundLayers: readonly string[];
  /** Applicable WCAG AA contrast threshold. */
  threshold: ContrastThreshold;
  /** Human-readable description for diagnostics. */
  description: string;
}

/** Resolved token map for a theme: token name → raw value string. */
export type TokenValues = Readonly<Record<string, string>>;

// ---------------------------------------------------------------------------
// Colour parsing
// ---------------------------------------------------------------------------

// Hex literal forms supported: #rgb, #rgba, #rrggbb, #rrggbbaa.
const HEX_3 = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i;
const HEX_4 = /^#([0-9a-f])([0-9a-f])([0-9a-f])([0-9a-f])$/i;
const HEX_6 = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i;
const HEX_8 = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i;

// Functional rgb()/rgba() form, accepting integer or decimal channels and an
// optional alpha in [0,1]. The legacy comma-separated form is used by the
// tokens.css file (e.g. `rgba(255, 255, 255, 0.9)`) so that's all we need.
const RGB_FUNC =
  /^rgba?\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*(?:,\s*(-?\d+(?:\.\d+)?)\s*)?\)$/i;

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function clampChannel(value: number): number {
  return clamp(value, 0, 255);
}

function clampAlpha(value: number): number {
  return clamp(value, 0, 1);
}

function hexPairToInt(hex: string): number {
  return parseInt(hex, 16);
}

/**
 * Parse a CSS colour string into an {@link RGBAColor}.
 *
 * Supports the colour formats actually used by `styles/tokens.css`:
 *  - `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa` hex literals
 *  - `rgb(r, g, b)` and `rgba(r, g, b, a)` functional notation
 *
 * Throws `Error` for any other input so callers cannot silently feed unparsed
 * strings into the contrast pipeline.
 */
export function parseColor(input: string): RGBAColor {
  const value = input.trim();

  const hex8 = HEX_8.exec(value);
  if (hex8 !== null) {
    return {
      r: hexPairToInt(hex8[1]),
      g: hexPairToInt(hex8[2]),
      b: hexPairToInt(hex8[3]),
      a: hexPairToInt(hex8[4]) / 255,
    };
  }

  const hex6 = HEX_6.exec(value);
  if (hex6 !== null) {
    return {
      r: hexPairToInt(hex6[1]),
      g: hexPairToInt(hex6[2]),
      b: hexPairToInt(hex6[3]),
      a: 1,
    };
  }

  const hex4 = HEX_4.exec(value);
  if (hex4 !== null) {
    return {
      r: hexPairToInt(hex4[1] + hex4[1]),
      g: hexPairToInt(hex4[2] + hex4[2]),
      b: hexPairToInt(hex4[3] + hex4[3]),
      a: hexPairToInt(hex4[4] + hex4[4]) / 255,
    };
  }

  const hex3 = HEX_3.exec(value);
  if (hex3 !== null) {
    return {
      r: hexPairToInt(hex3[1] + hex3[1]),
      g: hexPairToInt(hex3[2] + hex3[2]),
      b: hexPairToInt(hex3[3] + hex3[3]),
      a: 1,
    };
  }

  const rgbFunc = RGB_FUNC.exec(value);
  if (rgbFunc !== null) {
    const alphaRaw = rgbFunc[4];
    return {
      r: clampChannel(parseFloat(rgbFunc[1])),
      g: clampChannel(parseFloat(rgbFunc[2])),
      b: clampChannel(parseFloat(rgbFunc[3])),
      a: alphaRaw === undefined ? 1 : clampAlpha(parseFloat(alphaRaw)),
    };
  }

  throw new Error(`contrast.parseColor: unsupported colour format: "${input}"`);
}

// ---------------------------------------------------------------------------
// Alpha compositing
// ---------------------------------------------------------------------------

/**
 * Composite a foreground colour `fg` over a background colour `bg` using the
 * standard "source-over" Porter–Duff operation with straight (non-premultiplied)
 * alpha. The returned colour has the resulting alpha channel; when both
 * inputs are opaque the result is opaque.
 *
 *   out.rgb = (fg.rgb * fg.a + bg.rgb * bg.a * (1 - fg.a)) / out.a
 *   out.a   = fg.a + bg.a * (1 - fg.a)
 */
export function composite(fg: RGBAColor, bg: RGBAColor): RGBAColor {
  const fgA = clampAlpha(fg.a);
  const bgA = clampAlpha(bg.a);
  const outA = fgA + bgA * (1 - fgA);

  if (outA === 0) {
    // Both inputs are fully transparent; channels are meaningless.
    return { r: 0, g: 0, b: 0, a: 0 };
  }

  return {
    r: (fg.r * fgA + bg.r * bgA * (1 - fgA)) / outA,
    g: (fg.g * fgA + bg.g * bgA * (1 - fgA)) / outA,
    b: (fg.b * fgA + bg.b * bgA * (1 - fgA)) / outA,
    a: outA,
  };
}

// ---------------------------------------------------------------------------
// WCAG 2.1 luminance + contrast
// ---------------------------------------------------------------------------

/**
 * Linearise a single sRGB channel value in `[0, 1]` per the WCAG 2.1 formula:
 *
 *   c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
 *
 * (See https://www.w3.org/TR/WCAG21/#dfn-relative-luminance.)
 */
function sRGBChannelToLinear(channel: number): number {
  const c = clamp(channel, 0, 1);
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/**
 * Compute the WCAG 2.1 relative luminance of an opaque sRGB colour:
 *
 *   L = 0.2126 * R + 0.7152 * G + 0.0722 * B
 *
 * where R/G/B are the linearised channel values. Alpha is ignored; the caller
 * is responsible for compositing translucent colours onto an opaque
 * background first via {@link composite}.
 */
export function relativeLuminance(color: RGBAColor): number {
  const R = sRGBChannelToLinear(color.r / 255);
  const G = sRGBChannelToLinear(color.g / 255);
  const B = sRGBChannelToLinear(color.b / 255);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

/**
 * Compute the WCAG 2.1 contrast ratio between two opaque colours:
 *
 *   (Lmax + 0.05) / (Lmin + 0.05)
 *
 * Always returns a value in `[1, 21]`. Translucent inputs should be
 * composited onto opaque bases first; otherwise the alpha channel is ignored
 * and the ratio may not match what a user actually sees.
 */
export function contrastRatio(a: RGBAColor, b: RGBAColor): number {
  const L1 = relativeLuminance(a);
  const L2 = relativeLuminance(b);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

// ---------------------------------------------------------------------------
// Token resolution — parsed from styles/tokens.css at module load
// ---------------------------------------------------------------------------

/**
 * Extract every `--name: value;` declaration from the first CSS block whose
 * selector matches `selectorPattern`. Brace-depth aware so nested blocks
 * (e.g. `@media` rules) inside the matched ruleset would be skipped safely
 * even though `tokens.css` does not currently use them.
 */
function extractDeclarations(css: string, selectorPattern: RegExp): TokenValues {
  const map: Record<string, string> = {};
  const start = selectorPattern.exec(css);
  if (start === null) return map;

  const openBrace = css.indexOf("{", start.index);
  if (openBrace === -1) return map;

  let depth = 0;
  let closeBrace = -1;
  for (let i = openBrace; i < css.length; i++) {
    const ch = css[i];
    if (ch === "{") {
      depth++;
    } else if (ch === "}") {
      depth--;
      if (depth === 0) {
        closeBrace = i;
        break;
      }
    }
  }
  if (closeBrace === -1) return map;

  const body = css.slice(openBrace + 1, closeBrace);
  const decl = /(--[\w-]+)\s*:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = decl.exec(body)) !== null) {
    map[m[1].trim()] = m[2].trim();
  }
  return map;
}

const rootDeclarations = extractDeclarations(tokensCss, /:root\s*\{/);
const darkDeclarations = extractDeclarations(
  tokensCss,
  /\[data-theme\s*=\s*["']dark["']\]/,
);

/**
 * Per-theme resolved token maps, parsed from `styles/tokens.css` (the single
 * source of truth defined by task 4.1). The dark theme inherits every `:root`
 * token and then overlays its own declarations, mirroring CSS cascade
 * semantics; this is how a `[data-theme="dark"]` rule actually resolves at
 * runtime.
 */
export const THEME_TOKEN_VALUES: Readonly<Record<ThemeName, TokenValues>> = {
  light: { ...rootDeclarations },
  dark: { ...rootDeclarations, ...darkDeclarations },
};

/**
 * Resolve a single token name to its raw value for a given theme. Throws if
 * the token is undefined so missing tokens fail loudly rather than silently
 * producing zero-luminance black.
 */
export function resolveToken(
  name: string,
  theme: ThemeName,
  values: Readonly<Record<ThemeName, TokenValues>> = THEME_TOKEN_VALUES,
): string {
  const themeValues = values[theme];
  const raw = themeValues[name];
  if (raw === undefined) {
    throw new Error(
      `contrast.resolveToken: token "${name}" is not defined in the "${theme}" theme.`,
    );
  }
  return raw;
}

/**
 * Resolve a stack of background-layer tokens (top-to-bottom) into a single
 * opaque colour by alpha-compositing each layer over the layers beneath it.
 *
 * The deepest layer must be opaque (alpha === 1) in every theme — usually
 * `--color-bg` — so the composite has a defined opaque starting point.
 * Translucent layers in between (e.g. `--color-surface`, status backgrounds)
 * are composited up from the bottom.
 */
export function resolveBackgroundLayers(
  layers: readonly string[],
  theme: ThemeName,
  values: Readonly<Record<ThemeName, TokenValues>> = THEME_TOKEN_VALUES,
): RGBAColor {
  if (layers.length === 0) {
    throw new Error("contrast.resolveBackgroundLayers: backgroundLayers must not be empty.");
  }

  // Start from the deepest layer, which must be opaque.
  const baseName = layers[layers.length - 1];
  const base = parseColor(resolveToken(baseName, theme, values));
  if (base.a < 1) {
    throw new Error(
      `contrast.resolveBackgroundLayers: deepest background layer "${baseName}" ` +
        `in the "${theme}" theme must be opaque (alpha=1), got alpha=${base.a}.`,
    );
  }

  let cumulative: RGBAColor = base;
  for (let i = layers.length - 2; i >= 0; i--) {
    const above = parseColor(resolveToken(layers[i], theme, values));
    cumulative = composite(above, cumulative);
  }
  return cumulative;
}

/**
 * Compute the rendered WCAG 2.1 contrast ratio for a {@link TokenPairing} in
 * the given theme. The background stack is composited into an opaque colour
 * and any translucent foreground is composited over that effective background
 * before the ratio is computed — matching what the user actually sees.
 */
export function contrastForPairing(
  pairing: TokenPairing,
  theme: ThemeName,
  values: Readonly<Record<ThemeName, TokenValues>> = THEME_TOKEN_VALUES,
): number {
  const effectiveBg = resolveBackgroundLayers(pairing.backgroundLayers, theme, values);
  const fgRaw = parseColor(resolveToken(pairing.foreground, theme, values));
  const effectiveFg = fgRaw.a < 1 ? composite(fgRaw, effectiveBg) : fgRaw;
  return contrastRatio(effectiveFg, effectiveBg);
}

// ---------------------------------------------------------------------------
// Token-pairing map
// ---------------------------------------------------------------------------
//
// Each entry enumerates a foreground / background pairing that the
// application's component CSS actually renders together. The categories below
// follow the Property 6 split in design.md:
//
//   - normal-text       : 4.5:1 (Req 6.1) — body / label / placeholder /
//                         primary-button label / status-badge label /
//                         field validation text
//   - large-text        : 3:1   (Req 6.2) — card titles and summary-card
//                         numerals (>= 18pt or >= 14pt bold)
//   - status-graphical  : 3:1   (Req 6.2) — solid status colours used as
//                         badge borders, validation-input borders, and the
//                         critical-solid required-marker glyph
//   - focus-indicator   : 3:1   (Req 6.4) — accent-coloured focus outline
//                         shown with `outline-offset` so the adjacent colour
//                         is the surrounding card surface or page background
//
// The list intentionally enumerates every pairing actually used together in
// the codebase rather than every theoretical combination — Property 6 is
// about real on-screen contrast, not exhaustive colour cross-products.
// ---------------------------------------------------------------------------

const STATUS_STATES = ["healthy", "warning", "critical", "unknown"] as const;
type StatusKey = (typeof STATUS_STATES)[number];

function normalTextStatusPairings(): TokenPairing[] {
  return STATUS_STATES.map<TokenPairing>((state: StatusKey) => ({
    id: `status-${state}-on-status-${state}`,
    category: "normal-text",
    foreground: `--color-status-${state}-on`,
    backgroundLayers: [
      `--color-status-${state}`,
      "--color-surface",
      "--color-bg",
    ],
    threshold: 4.5,
    description:
      `${state[0].toUpperCase() + state.slice(1)} status badge label ` +
      `(${state}-on) on the translucent status background atop a card surface.`,
  }));
}

function statusGraphicalPairings(): TokenPairing[] {
  return STATUS_STATES.map<TokenPairing>((state: StatusKey) => ({
    id: `status-${state}-solid-vs-surface`,
    category: "status-graphical",
    foreground: `--color-status-${state}-solid`,
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 3,
    description:
      `${state[0].toUpperCase() + state.slice(1)} status border / icon glyph ` +
      `(solid colour) against the card surface.`,
  }));
}

/**
 * Canonical list of foreground / background token pairings used together by
 * the Operations Console, evaluated by the palette-contrast property test
 * (task 10.2, Property 6) against every active theme.
 */
export const TOKEN_PAIRINGS: readonly TokenPairing[] = [
  // -------------------------------------------------------------------------
  // Normal text (4.5:1) — Req 6.1
  // -------------------------------------------------------------------------
  {
    id: "text-on-bg",
    category: "normal-text",
    foreground: "--color-text",
    backgroundLayers: ["--color-bg"],
    threshold: 4.5,
    description: "Body text rendered directly on the page background.",
  },
  {
    id: "text-on-surface",
    category: "normal-text",
    foreground: "--color-text",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 4.5,
    description:
      "Body text rendered on the translucent card surface (Card, DataState, Field input).",
  },
  {
    id: "text-muted-on-bg",
    category: "normal-text",
    foreground: "--color-text-muted",
    backgroundLayers: ["--color-bg"],
    threshold: 4.5,
    description: "Muted body text rendered directly on the page background.",
  },
  {
    id: "text-muted-on-surface",
    category: "normal-text",
    foreground: "--color-text-muted",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 4.5,
    description:
      "Muted text rendered on the translucent card surface (DataState detail, Field helper, placeholder).",
  },
  {
    id: "accent-on-accent",
    category: "normal-text",
    foreground: "--color-accent-on",
    backgroundLayers: ["--color-accent"],
    threshold: 4.5,
    description: "Primary Button label rendered on the solid accent surface.",
  },
  {
    id: "bg-on-accent",
    category: "normal-text",
    foreground: "--color-bg",
    backgroundLayers: ["--color-accent"],
    threshold: 4.5,
    description:
      "DataState retry-button label (`var(--color-bg)`) rendered on the solid accent surface.",
  },
  {
    id: "validation-message-on-surface",
    category: "normal-text",
    foreground: "--color-status-critical-solid",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 4.5,
    description:
      "Field validation message text (critical-solid colour) rendered on the card surface.",
  },
  ...normalTextStatusPairings(),

  // -------------------------------------------------------------------------
  // Large text (3:1) — Req 6.2
  // Headings and summary numerals rendered in --color-text on a card surface.
  // -------------------------------------------------------------------------
  {
    id: "card-title-on-surface",
    category: "large-text",
    foreground: "--color-text",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 3,
    description:
      "Card title (`--font-size-xl` bold, ~21.6px) rendered on the card surface.",
  },
  {
    id: "summary-numeral-on-surface",
    category: "large-text",
    foreground: "--color-text",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 3,
    description:
      "Summary card numeral (`--font-size-2xl`, ~28.8px) rendered on the card surface.",
  },

  // -------------------------------------------------------------------------
  // Status graphical elements (3:1) — Req 6.2
  // Solid status colours used as badge borders / icon glyphs against the
  // card surface they sit on.
  // -------------------------------------------------------------------------
  ...statusGraphicalPairings(),

  // -------------------------------------------------------------------------
  // Focus indicator (3:1) — Req 6.4
  // Visible focus ring is `outline: var(--border-width-focus) solid
  // var(--color-accent)` shown with `outline-offset` so the colour adjacent
  // to the unfocused control is whatever the control is rendered on top of
  // (the card surface, or the page background for top-level controls).
  // -------------------------------------------------------------------------
  {
    id: "focus-accent-vs-bg",
    category: "focus-indicator",
    foreground: "--color-accent",
    backgroundLayers: ["--color-bg"],
    threshold: 3,
    description:
      "Focus outline (accent) against the page background — top-level controls and skip link.",
  },
  {
    id: "focus-accent-vs-surface",
    category: "focus-indicator",
    foreground: "--color-accent",
    backgroundLayers: ["--color-surface", "--color-bg"],
    threshold: 3,
    description:
      "Focus outline (accent) against the card surface — controls rendered inside Cards/Fields.",
  },
];
