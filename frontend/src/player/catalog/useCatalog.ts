import { useCallback, useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import type {
  CardType,
  PlayerCatalogCard,
  PlayerCatalogCriteria,
} from "../../api/types";

export type CardTypesState =
  | { status: "loading" }
  | { status: "ready"; cardTypes: CardType[] }
  | { status: "error"; error: unknown };

/* Tipos de carta para el filtro. */
export function useCardTypes() {
  const { playerCatalog } = useApi();
  const [state, setState] = useState<CardTypesState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    playerCatalog.cardTypes().then(
      (cardTypes) => {
        if (!cancelled) setState({ status: "ready", cardTypes });
      },
      (error: unknown) => {
        if (!cancelled) setState({ status: "error", error });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [playerCatalog, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, reload };
}

interface CatalogState {
  status: "idle" | "searching" | "loadingMore" | "done" | "error";
  items: PlayerCatalogCard[];
  nextCursor: number | null;
  error: unknown;
}

const INITIAL: CatalogState = {
  status: "idle",
  items: [],
  nextCursor: null,
  error: null,
};

/* Consulta el catálogo por páginas y recuerda los filtros para pedir las siguientes. */
export function useCatalog() {
  const { playerCatalog } = useApi();
  const [state, setState] = useState<CatalogState>(INITIAL);
  const criteriaRef = useRef<PlayerCatalogCriteria>({});
  // Solo cuenta la consulta más reciente, aunque otra anterior responda después.
  const latest = useRef(0);

  const search = useCallback(
    async (criteria: PlayerCatalogCriteria = criteriaRef.current) => {
      const request = ++latest.current;
      criteriaRef.current = criteria;
      setState({ ...INITIAL, status: "searching" });
      try {
        const page = await playerCatalog.search(criteria, null);
        if (request !== latest.current) return;
        setState({
          status: "done",
          items: page.items,
          nextCursor: page.next_cursor,
          error: null,
        });
      } catch (error) {
        if (request === latest.current)
          setState({ ...INITIAL, status: "error", error });
      }
    },
    [playerCatalog],
  );

  const loadMore = useCallback(
    async (cursor: number) => {
      const request = ++latest.current;
      setState((current) => ({ ...current, status: "loadingMore", error: null }));
      try {
        const page = await playerCatalog.search(criteriaRef.current, cursor);
        if (request !== latest.current) return;
        setState((current) => ({
          status: "done",
          items: [...current.items, ...page.items],
          nextCursor: page.next_cursor,
          error: null,
        }));
      } catch (error) {
        // Se conservan las cartas ya cargadas, para poder reintentar solo esta página.
        if (request === latest.current) {
          setState((current) => ({ ...current, status: "error", error }));
        }
      }
    },
    [playerCatalog],
  );

  return { state, search, loadMore };
}
