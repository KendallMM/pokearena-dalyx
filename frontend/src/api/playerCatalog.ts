import type { HttpClient } from "./httpClient";
import type { PlayerCatalogCriteria, PlayerCatalogPage, References } from "./types";

/* Nombres de los filtros en la API. Los que no están definidos no se envían. */
function toQuery(criteria: PlayerCatalogCriteria, cursor: number | null): string {
  const query = new URLSearchParams();
  const params: Record<string, string | number | null | undefined> = {
    card_type: criteria.cardType,
    cost_min: criteria.costMin,
    cost_max: criteria.costMax,
    owned_only: criteria.ownedOnly ? "true" : undefined,
    last_id: cursor,
  };
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) query.append(name, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

/* Catálogo y colección del jugador. */
export interface PlayerCatalogApi {
  /* Tipos, rarezas y habilidades para los filtros. */
  references(): Promise<References>;
  /* Una página del catálogo. El cursor es el next_cursor de la página anterior. */
  search(
    criteria: PlayerCatalogCriteria,
    cursor: number | null,
  ): Promise<PlayerCatalogPage>;
  /* Descarga la imagen de una carta desde su image_url. */
  image(imageUrl: string): Promise<Blob>;
}

export function createPlayerCatalogApi(http: HttpClient): PlayerCatalogApi {
  return {
    references: () => http.getCached<References>("/v1/referencias"),
    search: (criteria, cursor) =>
      http.getJson<PlayerCatalogPage>(`/v1/cartas${toQuery(criteria, cursor)}`),
    image: (imageUrl) => http.getBlob(imageUrl),
  };
}
