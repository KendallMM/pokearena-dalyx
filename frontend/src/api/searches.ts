import type { HttpClient } from "./httpClient";

export interface MatchSearch {
  id: string;
  deck_id: string;
  mode: "ranked" | "tournament";
  status: "waiting" | "reserved" | "found" | "cancelled";
  created_at: string;
  match_id: string | null;
  error: string | null;
}

export function createSearchesApi(http: HttpClient) {
  return {
    current: () => http.getJson<MatchSearch | null>("/v1/busquedas/actual"),
    get: (id: string) =>
      http.getJson<MatchSearch>(`/v1/busquedas/${encodeURIComponent(id)}`),
    enter: (deckId: string, key: string) =>
      http.postJson<MatchSearch>(
        "/v1/busquedas",
        { deck_id: deckId },
        { "Idempotency-Key": key },
      ),
    cancel: (id: string) =>
      http.postJson<MatchSearch>(
        `/v1/busquedas/${encodeURIComponent(id)}/cancelar`,
        {},
      ),
  };
}
