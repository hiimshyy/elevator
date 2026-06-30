import { forwardRef, type ButtonHTMLAttributes, type ForwardedRef } from "react";

import styles from "./Button.module.css";

/**
 * Button — Reusable UI primitive (Requirement 3.8).
 *
 * - Three token-driven variants: primary, secondary, ghost.
 * - Guarantees a visible focus ring with >= 3:1 contrast (Requirement 6.4).
 * - Guarantees a minimum 44x44px hit area for touch input (Requirement 6.5).
 * - Forwards refs so callers can imperatively focus the underlying button.
 * - Pass-through props let callers wire `type`, `disabled`, `aria-*`,
 *   `onClick`, `name`, `form`, `data-*`, etc.
 */

/** Visual variant of the button. */
export type ButtonVariant = "primary" | "secondary" | "ghost";

/**
 * Props accepted by {@link Button}. Extends the standard
 * `<button>` HTML attributes so every native button feature is supported.
 */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual emphasis level. Defaults to `"primary"`. */
  variant?: ButtonVariant;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
};

function ButtonImpl(
  { variant = "primary", type, className, ...rest }: ButtonProps,
  ref: ForwardedRef<HTMLButtonElement>,
): JSX.Element {
  // Default `type` to "button" so the control doesn't accidentally submit a
  // surrounding form. Callers that need `type="submit"` pass it explicitly.
  const resolvedType: ButtonProps["type"] = type ?? "button";

  const composedClassName = [styles.button, VARIANT_CLASS[variant], className]
    .filter((part): part is string => Boolean(part))
    .join(" ");

  return (
    <button
      {...rest}
      ref={ref}
      type={resolvedType}
      className={composedClassName}
    />
  );
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(ButtonImpl);
Button.displayName = "Button";
