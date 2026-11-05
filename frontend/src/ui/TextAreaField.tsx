import { Field } from "./Field";

interface Props {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  required?: boolean;
  maxLength?: number;
  disabled?: boolean;
}

export function TextAreaField({
  id,
  label,
  value,
  onChange,
  error,
  hint,
  required,
  maxLength,
  disabled,
}: Props) {
  return (
    <Field id={id} label={label} required={required} hint={hint} error={error}>
      {(control) => (
        <textarea
          {...control}
          className="input input--multiline"
          rows={3}
          maxLength={maxLength}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  );
}
