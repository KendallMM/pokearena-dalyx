/** Indicador de carga con texto, para no depender solo de la animación. */
export function Spinner({ label }: { label: string }) {
  return (
    <p className="spinner" role="status">
      <span className="spinner__dot" aria-hidden="true" />
      {label}
    </p>
  );
}
