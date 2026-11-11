import type { PlayerCatalogCriteria } from "../../api/types";
import { COST_RANGE, parseInteger } from "../../admin/cards/cardRules";

/* Filtros del catálogo. Vacío significa que el filtro no se usa. */
export interface CatalogFilterValues {
  cardType: string;
  costMin: string;
  costMax: string;
  ownedOnly: boolean;
}

export type CatalogFilterField = "cardType" | "costMin" | "costMax";
export type CatalogFilterErrors = Partial<Record<CatalogFilterField, string>>;

export const EMPTY_CATALOG_FILTERS: CatalogFilterValues = {
  cardType: "",
  costMin: "",
  costMax: "",
  ownedOnly: false,
};

function checkCost(text: string, label: string): string | undefined {
  if (!text.trim()) return undefined;
  const value = parseInteger(text);
  if (value === null) return `${label} debe ser un número entero.`;
  if (value < COST_RANGE.min || value > COST_RANGE.max) {
    return `${label} debe estar entre ${COST_RANGE.min} y ${COST_RANGE.max}.`;
  }
  return undefined;
}

/* Respuesta rápida antes de consultar; las reglas de verdad las aplica el servidor. */
export function validateCatalogFilters(
  values: CatalogFilterValues,
): CatalogFilterErrors {
  const errors: CatalogFilterErrors = {
    costMin: checkCost(values.costMin, "El costo mínimo"),
    costMax: checkCost(values.costMax, "El costo máximo"),
  };
  const low = parseInteger(values.costMin);
  const high = parseInteger(values.costMax);
  if (
    !errors.costMin &&
    !errors.costMax &&
    low !== null &&
    high !== null &&
    low > high
  ) {
    errors.costMin = "El costo mínimo no puede ser mayor que el máximo.";
  }
  return errors;
}

/* Arma los filtros de la consulta. Solo se llama con valores ya validados. */
export function toCatalogCriteria(values: CatalogFilterValues): PlayerCatalogCriteria {
  return {
    cardType: values.cardType || undefined,
    costMin: parseInteger(values.costMin) ?? undefined,
    costMax: parseInteger(values.costMax) ?? undefined,
    ownedOnly: values.ownedOnly || undefined,
  };
}

const FIELD_BY_API_NAME: Record<string, CatalogFilterField> = {
  card_type: "cardType",
  cost: "costMin",
  cost_min: "costMin",
  cost_max: "costMax",
};

/* Filtro que corresponde al campo que indica la API. */
export function catalogFieldFromApi(
  apiField: string | null,
): CatalogFilterField | null {
  return apiField ? (FIELD_BY_API_NAME[apiField] ?? null) : null;
}

/* Texto de la marca de posesión de cada carta. */
export function copiesText(copies: number): string {
  if (copies === 0) return "No la tienes";
  return copies === 1 ? "Tienes 1 copia" : `Tienes ${copies} copias`;
}
