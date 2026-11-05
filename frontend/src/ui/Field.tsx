import type { ReactNode } from "react";

/** Atributos de accesibilidad que cada campo debe poner en su control. */
export interface FieldControlProps {
  id: string;
  "aria-invalid": boolean;
  "aria-describedby": string | undefined;
  "aria-required": boolean;
}

interface Props {
  id: string;
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: (control: FieldControlProps) => ReactNode;
}

/** Etiqueta, ayuda y error de un campo, unidos al control para lectores de pantalla. */
export function Field({ id, label, required = false, hint, error, children }: Props) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label htmlFor={id} className="field__label">
        {label}
        {required && (
          <span className="field__required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {hint && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
      {children({
        id,
        "aria-invalid": Boolean(error),
        "aria-describedby": describedBy,
        "aria-required": required,
      })}
      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}
