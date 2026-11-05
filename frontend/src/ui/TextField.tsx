import type { HTMLInputTypeAttribute } from "react";

import { Field } from "./Field";

interface Props {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  required?: boolean;
  type?: HTMLInputTypeAttribute;
  inputMode?: "text" | "numeric";
  maxLength?: number;
  autoComplete?: string;
  disabled?: boolean;
}

export function TextField({
  id,
  label,
  value,
  onChange,
  error,
  hint,
  required,
  type = "text",
  inputMode,
  maxLength,
  autoComplete,
  disabled,
}: Props) {
  return (
    <Field id={id} label={label} required={required} hint={hint} error={error}>
      {(control) => (
        <input
          {...control}
          className="input"
          type={type}
          inputMode={inputMode}
          maxLength={maxLength}
          autoComplete={autoComplete}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  );
}
