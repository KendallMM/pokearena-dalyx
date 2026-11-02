import { Field } from "./Field";

export interface SelectOption {
  value: string;
  label: string;
}

interface Props {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder: string;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
}

export function SelectField({
  id,
  label,
  value,
  options,
  onChange,
  placeholder,
  error,
  hint,
  required,
  disabled,
}: Props) {
  return (
    <Field id={id} label={label} required={required} hint={hint} error={error}>
      {(control) => (
        <select
          {...control}
          className="input"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{placeholder}</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}
