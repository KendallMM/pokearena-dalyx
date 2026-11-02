/** Tipos del contrato de la API. Se agregan aquí al conectar cada pantalla. */

/** Forma de toda respuesta de error de la API. */
export interface ApiErrorBody {
  code: string;
  message: string;
  field: string | null;
  correlation_id: string | null;
}

export interface CardType {
  code: string;
  name: string;
}

export interface Rarity {
  code: string;
  name: string;
}

export interface Ability {
  code: string;
  name: string;
  /** Código del tipo al que afecta. Nulo significa todos los tipos. */
  affected_card_type: string | null;
}

/** GET /admin/referencias (los efectos de ubicación los usará la pantalla de ubicaciones). */
export interface References {
  card_types: CardType[];
  rarities: Rarity[];
  abilities: Ability[];
}

/** Datos del formulario de Crear carta, ya validados. */
export interface CreateCardInput {
  name: string;
  cost: number;
  power: number;
  cardType: string;
  rarity: string;
  ability: string;
  image: File;
}

/** Respuesta 202 de POST /admin/cartas. */
export interface CreateCardResult {
  code: string;
  status: string;
  message: string;
  /** Verdadero si la API devolvió la respuesta guardada de una operación repetida. */
  replayed: boolean;
}
