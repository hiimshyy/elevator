/**
 * Field + TextInput / Select / Textarea — reusable form primitives.
 *
 * Requirements:
 *  - 3.8 reusable form components (single source of truth for label, input,
 *        and validation message structure).
 *  - 6.5 minimum 44x44px touch target — enforced via CSS min-height token
 *        calc in Field.css.
 *  - 6.8 validation messages linked via aria-describedby exposing full text —
 *        when validationMessage is provided, it is rendered in an element
 *        with a stable id and the input wires aria-describedby to that id.
 *
 * Tokens are referenced only through Field.css (var(--token)); no hard-coded
 * color or rem literals appear here.
 */

import {
  useId,
  type ChangeEvent,
  type FocusEvent,
  type ReactNode,
} from "react";

import "./Field.css";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

/**
 * Forwarded ARIA props common to every form primitive.
 * `aria-describedby` here is the caller-provided extra; the field
 * automatically prepends its helper/validation message ids.
 */
interface AriaProps {
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
}

/** Props shared by every primitive (TextInput / Select / Textarea). */
interface CommonFieldProps extends AriaProps {
  /** Explicit id for the control. Auto-generated via useId() when absent. */
  id?: string;
  /** Visible label rendered inside an associated <label htmlFor=id>. */
  label: ReactNode;
  /** HTML form-field name. */
  name?: string;
  /** Marks the field required and renders a visual marker on the label. */
  required?: boolean;
  /** Disables the control. */
  disabled?: boolean;
  /** Optional helper text rendered below the control, linked via describedby. */
  helperText?: ReactNode;
  /**
   * Validation message. When non-empty:
   *   - rendered in an element with a stable id
   *   - the control's aria-describedby references that id
   *   - the control receives aria-invalid="true"
   */
  validationMessage?: string;
  /** Extra class name applied to the outer wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Field — primitive wrapper
// ---------------------------------------------------------------------------

interface FieldProps {
  /** id of the control inside `children`; bound to the <label htmlFor>. */
  controlId: string;
  label: ReactNode;
  required?: boolean;
  helperText?: ReactNode;
  helperTextId?: string;
  validationMessage?: string;
  validationMessageId?: string;
  className?: string;
  children: ReactNode;
}

/**
 * Layout wrapper for a form control.
 * Renders the <label>, the control(s) (as children), then optional helper
 * text and validation message in stable-id elements.
 *
 * Exposed publicly so callers with custom controls (e.g. checkbox groups,
 * date pickers) can compose the same label/validation structure.
 */
export function Field({
  controlId,
  label,
  required,
  helperText,
  helperTextId,
  validationMessage,
  validationMessageId,
  className,
  children,
}: FieldProps): JSX.Element {
  const wrapperClass = ["field", className].filter(Boolean).join(" ");

  return (
    <div className={wrapperClass}>
      <label htmlFor={controlId} className="field__label">
        <span>{label}</span>
        {required ? (
          <span aria-hidden="true" className="field__required-marker">
            *
          </span>
        ) : null}
      </label>
      {children}
      {helperText ? (
        <span id={helperTextId} className="field__helper">
          {helperText}
        </span>
      ) : null}
      {validationMessage ? (
        <span id={validationMessageId} className="field__validation">
          {validationMessage}
        </span>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compose the final aria-describedby token list.
 * Order: helper id (if any), validation id (if any), caller-supplied extra.
 * Returns undefined when no parts apply so the attribute is omitted.
 */
function buildDescribedBy(
  helperId: string | undefined,
  hasHelper: boolean,
  validationId: string | undefined,
  hasValidation: boolean,
  extra: string | undefined,
): string | undefined {
  const parts: string[] = [];
  if (hasHelper && helperId) parts.push(helperId);
  if (hasValidation && validationId) parts.push(validationId);
  if (extra) parts.push(extra);
  return parts.length > 0 ? parts.join(" ") : undefined;
}

// ---------------------------------------------------------------------------
// TextInput
// ---------------------------------------------------------------------------

export type TextInputType =
  | "text"
  | "email"
  | "password"
  | "number"
  | "tel"
  | "url"
  | "search";

export interface TextInputProps extends CommonFieldProps {
  type?: TextInputType;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void;
  placeholder?: string;
  autoComplete?: string;
  inputMode?:
    | "none"
    | "text"
    | "decimal"
    | "numeric"
    | "tel"
    | "search"
    | "email"
    | "url";
  pattern?: string;
  minLength?: number;
  maxLength?: number;
}

export function TextInput(props: TextInputProps): JSX.Element {
  const reactId = useId();
  const inputId = props.id ?? `text-input-${reactId}`;
  const helperId = `${inputId}-helper`;
  const messageId = `${inputId}-validation`;

  const hasHelper = props.helperText !== undefined && props.helperText !== null;
  const hasValidation =
    typeof props.validationMessage === "string" && props.validationMessage.length > 0;

  const describedBy = buildDescribedBy(
    helperId,
    hasHelper,
    messageId,
    hasValidation,
    props["aria-describedby"],
  );

  return (
    <Field
      controlId={inputId}
      label={props.label}
      required={props.required}
      helperText={props.helperText}
      helperTextId={helperId}
      validationMessage={props.validationMessage}
      validationMessageId={messageId}
      className={props.className}
    >
      <input
        id={inputId}
        name={props.name}
        type={props.type ?? "text"}
        className="field__input"
        value={props.value}
        onChange={props.onChange}
        onBlur={props.onBlur}
        placeholder={props.placeholder}
        required={props.required}
        disabled={props.disabled}
        autoComplete={props.autoComplete}
        inputMode={props.inputMode}
        pattern={props.pattern}
        minLength={props.minLength}
        maxLength={props.maxLength}
        aria-label={props["aria-label"]}
        aria-labelledby={props["aria-labelledby"]}
        aria-describedby={describedBy}
        aria-invalid={hasValidation ? true : undefined}
        aria-required={props.required ? true : undefined}
      />
    </Field>
  );
}

// ---------------------------------------------------------------------------
// Select
// ---------------------------------------------------------------------------

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends CommonFieldProps {
  options: SelectOption[];
  value: string;
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onBlur?: (event: FocusEvent<HTMLSelectElement>) => void;
  /**
   * Placeholder rendered as a disabled empty-value option at the top of the
   * list when supplied. Mirrors text-input semantics.
   */
  placeholder?: string;
}

export function Select(props: SelectProps): JSX.Element {
  const reactId = useId();
  const selectId = props.id ?? `select-${reactId}`;
  const helperId = `${selectId}-helper`;
  const messageId = `${selectId}-validation`;

  const hasHelper = props.helperText !== undefined && props.helperText !== null;
  const hasValidation =
    typeof props.validationMessage === "string" && props.validationMessage.length > 0;

  const describedBy = buildDescribedBy(
    helperId,
    hasHelper,
    messageId,
    hasValidation,
    props["aria-describedby"],
  );

  return (
    <Field
      controlId={selectId}
      label={props.label}
      required={props.required}
      helperText={props.helperText}
      helperTextId={helperId}
      validationMessage={props.validationMessage}
      validationMessageId={messageId}
      className={props.className}
    >
      <select
        id={selectId}
        name={props.name}
        className="field__select"
        value={props.value}
        onChange={props.onChange}
        onBlur={props.onBlur}
        required={props.required}
        disabled={props.disabled}
        aria-label={props["aria-label"]}
        aria-labelledby={props["aria-labelledby"]}
        aria-describedby={describedBy}
        aria-invalid={hasValidation ? true : undefined}
        aria-required={props.required ? true : undefined}
      >
        {props.placeholder ? (
          <option value="" disabled>
            {props.placeholder}
          </option>
        ) : null}
        {props.options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

// ---------------------------------------------------------------------------
// Textarea
// ---------------------------------------------------------------------------

export interface TextareaProps extends CommonFieldProps {
  value: string;
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onBlur?: (event: FocusEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  /** Default row count for the textarea. */
  rows?: number;
  maxLength?: number;
}

export function Textarea(props: TextareaProps): JSX.Element {
  const reactId = useId();
  const textareaId = props.id ?? `textarea-${reactId}`;
  const helperId = `${textareaId}-helper`;
  const messageId = `${textareaId}-validation`;

  const hasHelper = props.helperText !== undefined && props.helperText !== null;
  const hasValidation =
    typeof props.validationMessage === "string" && props.validationMessage.length > 0;

  const describedBy = buildDescribedBy(
    helperId,
    hasHelper,
    messageId,
    hasValidation,
    props["aria-describedby"],
  );

  return (
    <Field
      controlId={textareaId}
      label={props.label}
      required={props.required}
      helperText={props.helperText}
      helperTextId={helperId}
      validationMessage={props.validationMessage}
      validationMessageId={messageId}
      className={props.className}
    >
      <textarea
        id={textareaId}
        name={props.name}
        className="field__textarea"
        value={props.value}
        onChange={props.onChange}
        onBlur={props.onBlur}
        placeholder={props.placeholder}
        required={props.required}
        disabled={props.disabled}
        rows={props.rows}
        maxLength={props.maxLength}
        aria-label={props["aria-label"]}
        aria-labelledby={props["aria-labelledby"]}
        aria-describedby={describedBy}
        aria-invalid={hasValidation ? true : undefined}
        aria-required={props.required ? true : undefined}
      />
    </Field>
  );
}
