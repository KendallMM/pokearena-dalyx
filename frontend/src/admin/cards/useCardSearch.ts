import { useCallback, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import type { CardSearchCriteria, CardSearchResult } from "../../api/types";

interface CardSearchState {
  status: "idle" | "searching" | "loadingMore" | "done" | "error";
  items: CardSearchResult[];
  nextCursor: number | null;
  error: unknown;
}

const INITIAL: CardSearchState = {
  status: "idle",
  items: [],
  nextCursor: null,
  error: null,
};

/* Consulta las cartas por páginas y recuerda los criterios para pedir las siguientes. */
export function useCardSearch() {
  const { cards } = useApi();
  const [state, setState] = useState<CardSearchState>(INITIAL);
  const criteriaRef = useRef<CardSearchCriteria>({});
  // Solo cuenta la consulta más reciente, aunque otra anterior responda después.
  const latest = useRef(0);

  const search = useCallback(
    async (criteria: CardSearchCriteria = criteriaRef.current) => {
      const request = ++latest.current;
      criteriaRef.current = criteria;
      setState({ ...INITIAL, status: "searching" });
      try {
        const page = await cards.search(criteria, null);
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
    [cards],
  );

  const loadMore = useCallback(
    async (cursor: number) => {
      const request = ++latest.current;
      setState((current) => ({ ...current, status: "loadingMore", error: null }));
      try {
        const page = await cards.search(criteriaRef.current, cursor);
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
    [cards],
  );

  return { state, search, loadMore };
}
