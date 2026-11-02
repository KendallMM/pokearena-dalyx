import type { CreateCardInput } from "../../api/types";

/** Valores permitidos según la historia Crear carta. El servidor los vuelve a validar. */
export const COST_RANGE = { min: 0, max: 10 } as const;
export const POWER_RANGE = { min: -20, max: 20 } as const;
export const NAME_MAX_LENGTH = 100;

export interface CardFormValues {
  name: string;
  /** Texto del campo; se convierte a número al validar. */
  cost: string;
  power: string;
  cardType: string;
  rarity: string;
  ability: string;
  image: File | null;
}

export type CardFormField = keyof CardFormValues;
export type CardFormErrors = Partial<Record<CardFormField, string>>;

export const EMPTY_CARD_FORM: CardFormValues = {
  name: "",
  cost: "",
  power: "",
  cardType: "",
  rarity: "",
  ability: "",
  image: null,
};

/** Convierte "5" o "-3" en número. Devuelve null si no es un entero. */
export function parseInteger(text: string): number | null {
  const clean = text.trim();
  return /^-?\d+$/.test(clean) ? Number(clean) : null;
}

function validateNumber(
  text: string,
  label: string,
  range: { min: number; max: number },
): string | undefined {
  if (!text.trim()) return `${label} es obligatorio.`;
  const value = parseInteger(text);
  if (value === null) return `${label} debe ser un número entero.`;
  if (value < range.min || value > range.max) {
    return `${label} debe estar entre ${range.min} y ${range.max}.`;
  }
  return undefined;
}

/**
 * Validación de formato antes de enviar (paso 17 de la secuencia). Da respuesta rápida
 * al administrador; las reglas de verdad las aplica el servidor.
 * La imagen se revisa aparte porque requiere leer el archivo.
 */
export function validateCardValues(values: CardFormValues): CardFormErrors {
  const errors: CardFormErrors = {};

  const name = values.name.trim();
  if (!name) errors.name = "El nombre es obligatorio.";
  else if (name.length > NAME_MAX_LENGTH) {
    errors.name = `El nombre no puede superar ${NAME_MAX_LENGTH} caracteres.`;
  }

  const cost = validateNumber(values.cost, "El costo", COST_RANGE);
  if (cost) errors.cost = cost;
  const power = validateNumber(values.power, "El poder", POWER_RANGE);
  if (power) errors.power = power;

  if (!values.cardType) errors.cardType = "Elige un tipo.";
  if (!values.rarity) errors.rarity = "Elige una rareza.";
  if (!values.ability) {
    errors.ability = "Elige una habilidad, aunque sea Sin Habilidad.";
  }
  if (!values.image) errors.image = "Adjunta la imagen de la carta.";
  return errors;
}

/** Arma lo que se envía a la API. Solo se llama con valores ya validados. */
export function toCreateCardInput(values: CardFormValues): CreateCardInput {
  if (!values.image) throw new Error("Falta la imagen de la carta.");
  return {
    name: values.name.trim(),
    cost: Number(values.cost.trim()),
    power: Number(values.power.trim()),
    cardType: values.cardType,
    rarity: values.rarity,
    ability: values.ability,
    image: values.image,
  };
}

const FIELD_BY_API_NAME: Record<string, CardFormField> = {
  name: "name",
  cost: "cost",
  power: "power",
  card_type: "cardType",
  rarity: "rarity",
  ability: "ability",
  image: "image",
};

/** Nombre del campo del formulario que corresponde al campo que indica la API. */
export function formFieldFromApi(apiField: string | null): CardFormField | null {
  return apiField ? (FIELD_BY_API_NAME[apiField] ?? null) : null;
}
