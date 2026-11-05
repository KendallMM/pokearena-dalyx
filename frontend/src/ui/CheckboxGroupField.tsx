interface Props {
  /* El primer cuadro usa este id, para poder llevarle el foco desde el resumen de errores. */
  id: string;
  label: string;
  options: number[];
  selected: number[];
  onChange: (selected: number[]) => void;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
}

/* Varias opciones numéricas que se pueden marcar a la vez. */
export function CheckboxGroupField({
  id,
  label,
  options,
  selected,
  onChange,
  error,
  hint,
  required = false,
  disabled,
}: Props) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  function toggle(option: number, checked: boolean) {
    const others = selected.filter((value) => value !== option);
    onChange(checked ? [...others, option].sort((a, b) => a - b) : others);
  }

  return (
    <fieldset
      className={`field checkbox-group${error ? " field--invalid" : ""}`}
      aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
    >
      <legend className="field__label">
        {label}
        {required && (
          <span className="field__required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </legend>
      {hint && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
      <div className="checkbox-group__options">
        {options.map((option, index) => (
          <label key={option} className="checkbox-group__option">
            <input
              id={index === 0 ? id : undefined}
              type="checkbox"
              checked={selected.includes(option)}
              disabled={disabled}
              onChange={(event) => toggle(option, event.target.checked)}
            />
            {option}
          </label>
        ))}
      </div>
      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
    </fieldset>
  );
}
