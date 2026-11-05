import { Field } from "./Field";
import { useObjectUrl } from "./useObjectUrl";

interface Props {
  id: string;
  label: string;
  file: File | null;
  onChange: (file: File | null) => void;
  accept: string;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
}

/* Selector de imagen con vista previa. */
export function ImageField({
  id,
  label,
  file,
  onChange,
  accept,
  error,
  hint,
  required,
  disabled,
}: Props) {
  const previewUrl = useObjectUrl(file);

  return (
    <Field id={id} label={label} required={required} hint={hint} error={error}>
      {(control) => (
        <>
          <input
            {...control}
            className="input input--file"
            type="file"
            accept={accept}
            disabled={disabled}
            onChange={(event) => onChange(event.target.files?.[0] ?? null)}
          />
          {file && (
            <div className="image-preview">
              {previewUrl && (
                <img src={previewUrl} alt={`Vista previa de ${file.name}`} />
              )}
              <p className="image-preview__name">
                {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          )}
        </>
      )}
    </Field>
  );
}
