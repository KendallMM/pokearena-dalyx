import type { HttpClient } from "./httpClient";
import type { CreateCardInput, CreateCardResult } from "./types";

export interface CardsApi {
  /**
   * Crea una carta. La llave identifica la operación: repetirla con la misma llave
   * no crea otra carta, aunque el reintento sea por una falla de red.
   */
  create(input: CreateCardInput, idempotencyKey: string): Promise<CreateCardResult>;
}

export function createCardsApi(http: HttpClient): CardsApi {
  return {
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
