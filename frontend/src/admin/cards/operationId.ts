import { useCallback, useRef } from "react";

/** Identificador único de una operación (para el encabezado Idempotency-Key). */
export function newOperationId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID solo existe en contextos seguros (HTTPS o localhost).
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Mantiene la llave de la operación en curso. Mientras el formulario no cambie, un
 * reintento (por ejemplo tras una falla de red) usa la misma llave y el servidor no
 * crea una carta duplicada. Si el administrador cambia algo, o la operación termina,
 * la llave se descarta y la siguiente operación recibe una nueva.
 */
export function useOperationKey() {
  const keyRef = useRef<string | null>(null);
  const current = useCallback(() => {
    if (keyRef.current === null) keyRef.current = newOperationId();
    return keyRef.current;
  }, []);
  const reset = useCallback(() => {
    keyRef.current = null;
  }, []);
  return { current, reset };
}
