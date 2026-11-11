/* Tipos del contrato de la API. Se agregan aquí al conectar cada pantalla. */

/* Forma de toda respuesta de error de la API. */
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
  /* Código del tipo al que afecta. Nulo significa todos los tipos. */
  affected_card_type: string | null;
}

export interface EffectParameter {
  name: string;
  kind: "integer" | "card_type" | "integer_list";
  required: boolean;
  /* Mínimo y máximo permitidos, si aplican. */
  minimum: number | null;
  maximum: number | null;
}

export interface LocationEffectType {
  code: string;
  name: string;
  parameters: EffectParameter[];
}

/* GET /admin/referencias */
export interface References {
  card_types: CardType[];
  rarities: Rarity[];
  abilities: Ability[];
  location_effect_types: LocationEffectType[];
}

/* Datos del formulario de Crear carta, ya validados. */
export interface CreateCardInput {
  name: string;
  cost: number;
  power: number;
  cardType: string;
  rarity: string;
  ability: string;
  image: File;
}

/* Respuesta 202 de POST /admin/cartas. */
export interface CreateCardResult {
  code: string;
  status: string;
  message: string;
  /* Verdadero si la API devolvió la respuesta guardada de una operación repetida. */
  replayed: boolean;
}

/* Filtros de GET /admin/cartas. Todos son opcionales y los activos se cumplen a la vez. */
export interface CardSearchCriteria {
  code?: string;
  name?: string;
  cardType?: string;
  rarity?: string;
  ability?: string;
  costMin?: number;
  costMax?: number;
  powerMin?: number;
  powerMax?: number;
}

/* Una carta del resultado de la búsqueda. */
export interface CardSearchResult {
  code: string;
  name: string;
  cost: number;
  power: number;
  card_type: CardType;
  rarity: Rarity;
  ability: Ability;
  /* Ruta de la versión grande de la imagen. Pide sesión. */
  image_url: string;
  image_status: string;
  /* Intentos fallidos de generar la versión pequeña. */
  thumbnail_attempts: number;
}

/* Una página de resultados. next_cursor es nulo en la última. */
export interface CardSearchPage {
  items: CardSearchResult[];
  next_cursor: number | null;
}

export type EnergyMode = "fixed" | "per_card";

/* Datos del formulario de Crear ubicación, ya validados. */
export interface CreateLocationInput {
  name: string;
  description: string;
  cardLimit: number;
  energyMode: EnergyMode;
  energyAmount: number;
  /* Nulo significa que la ubicación no tiene efecto. */
  effect: {
    type: string;
    parameters: Record<string, string | number | number[]>;
  } | null;
  image: File;
}

/* Respuesta 202 de POST /admin/ubicaciones. */
export interface CreateLocationResult {
  id: number;
  status: string;
  message: string;
  /* Verdadero si la API devolvió la respuesta guardada de una operación repetida. */
  replayed: boolean;
}
export interface PlayerAccount {
  id: string;
  name: string;
  email: string;
  role: "player" | "content_admin" | "partner_admin";
  elo: number;
  cubes: number;
}

export interface InitialCollectionDelivery {
  status: "delivered" | "already_delivered" | "unavailable" | "pending";
  message: string;
}

export interface GoogleChallenge {
  client_id: string;
  nonce: string;
  expires_in: number;
}

export interface PlayerSession {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  expires_at: string;
  player: PlayerAccount;
  initial_collection: InitialCollectionDelivery;
}

/* Filtros de GET /v1/cartas. Todos opcionales; los activos se cumplen a la vez. */
export interface PlayerCatalogCriteria {
  cardType?: string;
  costMin?: number;
  costMax?: number;
  /* Solo las cartas que posee el jugador. */
  ownedOnly?: boolean;
}

/* Una carta del catálogo y cuántas copias tiene el jugador. */
export interface PlayerCatalogCard {
  code: string;
  name: string;
  cost: number;
  power: number;
  card_type: CardType;
  rarity: Rarity;
  ability: Ability;
  /* Ruta de la versión grande de la imagen. Pide sesión. */
  image_url: string;
  owned: boolean;
  copies: number;
}

/* Una página del catálogo. next_cursor es nulo en la última. */
export interface PlayerCatalogPage {
  items: PlayerCatalogCard[];
  next_cursor: number | null;
}
