import type { CardSearchCriteria } from "../../api/types";
import { COST_RANGE, NAME_MAX_LENGTH, parseInteger, POWER_RANGE } from "./cardRules";

/* Todos los filtros son opcionales. Para un valor exacto, se pone igual mínimo y máximo. */
export interface CardSearchValues {
  code: string;
  name: string;
  cardType: string;
  rarity: string;
  ability: string;
  costMin: string;
  costMax: string;
  powerMin: string;
  powerMax: string;
}

export type CardSearchField = keyof CardSearchValues;
export type CardSearchErrors = Partial<Record<CardSearchField, string>>;

export const EMPTY_CARD_SEARCH: CardSearchValues = {
  code: "",
  name: "",
  cardType: "",
  rarity: "",
  ability: "",
  costMin: "",
  costMax: "",
  powerMin: "",
  powerMax: "",
};

/* Un número opcional: vacío es válido y significa que el filtro no se usa. */
function checkNumber(
  text: string,
  label: string,
  range: { min: number; max: number },
): string | undefined {
  if (!text.trim()) return undefined;
  const value = parseInteger(text);
  if (value === null) return `${label} debe ser un número entero.`;
  if (value < range.min || value > range.max) {
    return `${label} debe estar entre ${range.min} y ${range.max}.`;
  }
  return undefined;
}

function isInverted(min: string, max: string): boolean {
  const low = parseInteger(min);
  const high = parseInteger(max);
  return low !== null && high !== null && low > high;
}

/* Respuesta rápida antes de consultar; las reglas de verdad las aplica el servidor. */
export function validateCardSearch(values: CardSearchValues): CardSearchErrors {
  const errors: CardSearchErrors = {};

  if (values.name.trim().length > NAME_MAX_LENGTH) {
    errors.name = `El nombre no puede superar ${NAME_MAX_LENGTH} caracteres.`;
  }

  errors.costMin = checkNumber(values.costMin, "El costo mínimo", COST_RANGE);
  errors.costMax = checkNumber(values.costMax, "El costo máximo", COST_RANGE);
  errors.powerMin = checkNumber(values.powerMin, "El poder mínimo", POWER_RANGE);
  errors.powerMax = checkNumber(values.powerMax, "El poder máximo", POWER_RANGE);

  if (!errors.costMin && isInverted(values.costMin, values.costMax)) {
    errors.costMin = "El costo mínimo no puede ser mayor que el máximo.";
  }
  if (!errors.powerMin && isInverted(values.powerMin, values.powerMax)) {
    errors.powerMin = "El poder mínimo no puede ser mayor que el máximo.";
  }
  return errors;
}

function optionalNumber(text: string): number | undefined {
  return parseInteger(text) ?? undefined;
}

/* Arma los criterios de la consulta. Solo se llama con valores ya validados. */
export function toCardSearchCriteria(values: CardSearchValues): CardSearchCriteria {
  return {
    code: values.code.trim() || undefined,
    name: values.name.trim() || undefined,
    cardType: values.cardType || undefined,
    rarity: values.rarity || undefined,
    ability: values.ability || undefined,
    costMin: optionalNumber(values.costMin),
    costMax: optionalNumber(values.costMax),
    powerMin: optionalNumber(values.powerMin),
    powerMax: optionalNumber(values.powerMax),
  };
}

const FIELD_BY_API_NAME: Record<string, CardSearchField> = {
  code: "code",
  name: "name",
  card_type: "cardType",
  rarity: "rarity",
  ability: "ability",
  // El servidor usa "cost" y "power" cuando el mínimo es mayor que el máximo.
  cost: "costMin",
  cost_min: "costMin",
  cost_max: "costMax",
  power: "powerMin",
  power_min: "powerMin",
  power_max: "powerMax",
};

/* Filtro que corresponde al campo que indica la API. */
export function searchFieldFromApi(apiField: string | null): CardSearchField | null {
  return apiField ? (FIELD_BY_API_NAME[apiField] ?? null) : null;
}
