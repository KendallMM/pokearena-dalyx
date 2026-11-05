import type { HttpClient } from "./httpClient";
import type { CreateLocationInput, CreateLocationResult } from "./types";

export interface LocationsApi {
  /*
   * Crea una ubicación. La llave identifica la operación: repetirla con la misma llave
   * no crea otra ubicación, aunque el reintento sea por una falla de red.
   */
  create(
    input: CreateLocationInput,
    idempotencyKey: string,
  ): Promise<CreateLocationResult>;
}

export function createLocationsApi(http: HttpClient): LocationsApi {
  return {
    async create(input, idempotencyKey) {
      const form = new FormData();
      form.append("name", input.name);
      form.append("description", input.description);
      form.append("card_limit", String(input.cardLimit));
      form.append("extra_energy_mode", input.energyMode);
      form.append("extra_energy_amount", String(input.energyAmount));
      if (input.effect) {
        form.append("effect_type", input.effect.type);
        // Va como texto JSON porque el formulario también lleva la imagen.
        form.append("effect_parameters", JSON.stringify(input.effect.parameters));
      }
      form.append("image", input.image);

      const { data, headers } = await http.postForm<
        Omit<CreateLocationResult, "replayed">
      >("/admin/ubicaciones", form, { "Idempotency-Key": idempotencyKey });
      return { ...data, replayed: headers.get("Idempotent-Replayed") === "true" };
    },
  };
}
