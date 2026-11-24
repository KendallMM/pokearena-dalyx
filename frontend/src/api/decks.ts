import type { HttpClient } from "./httpClient";
import type { CreatedDeck, PlayerDeck } from "./types";

/* Decks del jugador autenticado. */
export interface DecksApi {
  list(): Promise<PlayerDeck[]>;
  get(deckId: string): Promise<PlayerDeck>;
  /* Repetir la operación con la misma llave no crea otro deck. */
  create(name: string, cards: string[], idempotencyKey: string): Promise<CreatedDeck>;
}

export function createDecksApi(http: HttpClient): DecksApi {
  return {
    list: async () => (await http.getJson<{ items: PlayerDeck[] }>("/v1/mazos")).items,
    get: (deckId) =>
      http.getJson<PlayerDeck>(`/v1/mazos/${encodeURIComponent(deckId)}`),
    create: (name, cards, idempotencyKey) =>
      http.postJson<CreatedDeck>(
        "/v1/mazos",
        { name, cards },
        { "Idempotency-Key": idempotencyKey },
      ),
  };
}
