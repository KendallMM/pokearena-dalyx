import type { HttpClient } from "./httpClient";
import type {
  CardSearchCriteria,
  CardSearchPage,
  CreateCardInput,
  CreateCardResult,
} from "./types";

/* Nombres de los criterios en la API. Los que no están definidos no se envían. */
function toSearchQuery(criteria: CardSearchCriteria, cursor: number | null): string {
  const query = new URLSearchParams();
  const params: Record<string, string | number | null | undefined> = {
    code: criteria.code,
    name: criteria.name,
    card_type: criteria.cardType,
    rarity: criteria.rarity,
    ability: criteria.ability,
    cost_min: criteria.costMin,
    cost_max: criteria.costMax,
    power_min: criteria.powerMin,
    power_max: criteria.powerMax,
    last_id: cursor,
  };
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) query.append(name, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export interface CardsApi {
  /* Una página de cartas. El cursor es el next_cursor de la página anterior. */
  search(criteria: CardSearchCriteria, cursor: number | null): Promise<CardSearchPage>;
  /* Descarga la imagen de una carta desde el image_url que trae cada resultado. */
  image(imageUrl: string): Promise<Blob>;
  /**
   * Crea una carta. La llave identifica la operación: repetirla con la misma llave
   * no crea otra carta, aunque el reintento sea por una falla de red.
   */
  create(input: CreateCardInput, idempotencyKey: string): Promise<CreateCardResult>;
}

export function createCardsApi(http: HttpClient): CardsApi {
  return {
    search: (criteria, cursor) =>
      http.getJson<CardSearchPage>(`/admin/cartas${toSearchQuery(criteria, cursor)}`),

    image: (imageUrl) => http.getBlob(imageUrl),

    async create(input, idempotencyKey) {
      const form = new FormData();
      form.append("name", input.name);
      form.append("cost", String(input.cost));
      form.append("power", String(input.power));
      form.append("card_type", input.cardType);
      form.append("rarity", input.rarity);
      form.append("ability", input.ability);
      form.append("image", input.image);

      const { data, headers } = await http.postForm<Omit<CreateCardResult, "replayed">>(
        "/admin/cartas",
        form,
        { "Idempotency-Key": idempotencyKey },
      );
      return { ...data, replayed: headers.get("Idempotent-Replayed") === "true" };
    },
  };
}
