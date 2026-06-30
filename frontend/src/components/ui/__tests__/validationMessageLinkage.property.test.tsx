// Feature: ui-ux-responsive-redesign, Property 8: Validation messages are accessibly linked with full text
//
// Validates: Requirements 6.8
//
// Property 8 (from design.md):
//   For all validation message strings associated with a form input, the
//   rendered input references the message via an accessible description
//   (`aria-describedby`) whose referenced element exposes the complete
//   message text.
//
// Requirement 6.8 (from requirements.md):
//   "WHERE a form input has an associated validation message, THE
//   Operations_Console SHALL link the validation message to the input
//   through an accessible description reference that exposes the full
//   message text."
//
// Scope:
//   Property 8 is universally quantified over "validation message strings
//   associated with a form input". The Field.tsx module exposes three
//   primitives that accept a `validationMessage` prop — TextInput (input),
//   Select (select), Textarea (textarea) — so the property holds for the
//   implemented surface iff it holds for each of those primitives. Empty
//   and whitespace-only strings are excluded from the property: the Field
//   primitive intentionally suppresses `aria-describedby` when no message
//   is associated (there is nothing to link), which is correct behavior
//   for the "no message associated" case rather than a counter-example
//   to Property 8.

import * as fc from "fast-check";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Select, Textarea, TextInput } from "../Field";

// ---------------------------------------------------------------------------
// Variant table
// ---------------------------------------------------------------------------

type VariantId = "text-input" | "select" | "textarea";

interface VariantSpec {
  id: VariantId;
  /** Rendered interactive control tag the message must be linked to. */
  controlTagName: "INPUT" | "SELECT" | "TEXTAREA";
  /** Render the primitive with the supplied validation message. */
  render(message: string): JSX.Element;
}

const VARIANTS: VariantSpec[] = [
  {
    id: "text-input",
    controlTagName: "INPUT",
    render: (message) => (
      <TextInput
        label="Field label"
        value=""
        onChange={() => {
          /* no-op */
        }}
        validationMessage={message}
      />
    ),
  },
  {
    id: "select",
    controlTagName: "SELECT",
    render: (message) => (
      <Select
        label="Field label"
        value=""
        onChange={() => {
          /* no-op */
        }}
        validationMessage={message}
        options={[{ value: "a", label: "A" }]}
      />
    ),
  },
  {
    id: "textarea",
    controlTagName: "TEXTAREA",
    render: (message) => (
      <Textarea
        label="Field label"
        value=""
        onChange={() => {
          /* no-op */
        }}
        validationMessage={message}
      />
    ),
  },
];

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

describe("Property 8: Validation messages are accessibly linked with full text (Requirement 6.8)", () => {
  afterEach(() => {
    cleanup();
  });

  // Fixed-list arbitrary so the shrinker can name the failing variant.
  const arbVariant = fc.constantFrom(...VARIANTS);

  // Generate non-empty validation message strings. Mix `unicodeString` (covers
  // exotic code points, accents, CJK, emoji-adjacent runes — excludes lone
  // surrogates that React would reject) with `string` (ASCII-skewed shrink
  // targets) so the shrinker can land on small, human-readable counter-
  // examples. Filter out empty / whitespace-only messages: Property 8 only
  // applies when a message is *associated* with the input, and Field
  // intentionally suppresses `aria-describedby` when no message is provided.
  const arbMessage = fc
    .oneof(
      fc.unicodeString({ minLength: 1, maxLength: 64 }),
      fc.string({ minLength: 1, maxLength: 64 }),
    )
    .filter((s) => s.trim().length > 0);

  it("links the validation message to the control via aria-describedby and exposes the full text", () => {
    fc.assert(
      fc.property(arbVariant, arbMessage, (variant, message) => {
        // Always start each iteration with a clean DOM so prior renders do
        // not leak duplicate elements with colliding ids into our queries.
        cleanup();
        const { container } = render(variant.render(message));

        // 1. The variant produces a control of the expected DOM type.
        const control = container.querySelector(
          variant.controlTagName.toLowerCase(),
        ) as HTMLElement | null;
        expect(control).not.toBeNull();
        expect(control!.tagName).toBe(variant.controlTagName);

        // 2. The control exposes `aria-describedby` as a non-empty,
        //    whitespace-separated list of one or more ids.
        const describedBy = control!.getAttribute("aria-describedby");
        expect(describedBy).not.toBeNull();
        expect(describedBy!.length).toBeGreaterThan(0);
        const referencedIds = describedBy!.split(/\s+/).filter(Boolean);
        expect(referencedIds.length).toBeGreaterThanOrEqual(1);

        // 3. At least one referenced id resolves to an element in the
        //    rendered DOM whose textContent exposes the full validation
        //    message verbatim. We check every referenced id (not just the
        //    first) so the property remains robust if Field ever prepends
        //    additional describedby tokens (e.g. helper text) in the future.
        const messageHosts = referencedIds
          .map((id) => container.querySelector(`#${CSS.escape(id)}`))
          .filter((el): el is Element => el !== null);
        expect(messageHosts.length).toBeGreaterThanOrEqual(1);

        const fullTextExposed = messageHosts.some((host) =>
          (host.textContent ?? "").includes(message),
        );
        expect(fullTextExposed).toBe(true);

        // 4. The control is marked invalid — a related contract from
        //    Field.tsx that complements the linkage. Without it, assistive
        //    tech may not announce the linked description as a validation
        //    error.
        expect(control!.getAttribute("aria-invalid")).toBe("true");
      }),
      { numRuns: 120, verbose: false },
    );
  });
});
