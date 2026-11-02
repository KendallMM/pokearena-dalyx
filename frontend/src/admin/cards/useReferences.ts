import { useCallback, useEffect, useState } from "react";

import { useApi } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import type { References } from "../../api/types";

export type ReferencesState =
  | { status: "loading" }
  | { status: "ready"; references: References }
  | { status: "error"; error: ApiError | Error };

/** Carga los catálogos del formulario al abrirlo (parte A de la secuencia). */
export function useReferences() {
  const { references: api } = useApi();
  const [state, setState] = useState<ReferencesState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    api
      .load()
      .then((references) => {
        if (!cancelled) setState({ status: "ready", references });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            error: error instanceof Error ? error : new Error(String(error)),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, reload };
}
