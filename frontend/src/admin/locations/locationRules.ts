import type {
  CreateLocationInput,
  EffectParameter,
  EnergyMode,
  LocationEffectType,
} from "../../api/types";
import { parseInteger } from "../cards/cardRules";

/* Valores permitidos según la historia Crear ubicación. El servidor los vuelve a validar. */
export const NAME_MAX_LENGTH = 100;
export const DESCRIPTION_MAX_LENGTH = 500;
export const CARD_LIMIT_RANGE = { min: 0, max: 5 } as const;
export const MAX_EXTRA_ENERGY: Record<EnergyMode, number> = { fixed: 3, per_card: 2 };

export const ENERGY_MODE_LABELS: Record<EnergyMode, string> = {
  fixed: "Fija, por jugador",
  per_card: "Por cada carta propia",
};

/* El catálogo trae los nombres técnicos de los parámetros. */
const PARAMETER_LABELS: Record<string, string> = {
  amount: "Cantidad",
  card_type: "Tipo de carta",
  turns: "Turnos",
};

export function parameterLabel(name: string): string {
  return PARAMETER_LABELS[name] ?? name;
}

/* Texto del campo para números y tipos; lista de números para los turnos. */
export type EffectParameterValue = string | number[];

export interface LocationFormValues {
  name: string;
  description: string;
  cardLimit: string;
  energyMode: string;
  energyAmount: string;
  effectType: string;
  effectParameters: Record<string, EffectParameterValue>;
  image: File | null;
}

export type LocationValueField = Exclude<keyof LocationFormValues, "effectParameters">;
export type LocationFormField = LocationValueField | `parameter:${string}`;
export type LocationFormErrors = Partial<Record<LocationFormField, string>>;

export const EMPTY_LOCATION_FORM: LocationFormValues = {
  name: "",
  description: "",
  cardLimit: "",
  energyMode: "",
  energyAmount: "",
  effectType: "",
  effectParameters: {},
  image: null,
};

export function parameterField(name: string): LocationFormField {
  return `parameter:${name}`;
}

function isEnergyMode(mode: string): mode is EnergyMode {
  return mode in MAX_EXTRA_ENERGY;
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

function validateParameter(
  parameter: EffectParameter,
  value: EffectParameterValue | undefined,
): string | undefined {
  if (parameter.kind === "integer_list") {
    if (parameter.required && (!Array.isArray(value) || value.length === 0)) {
      return "Elige al menos una opción.";
    }
    return undefined;
  }
  const label = parameterLabel(parameter.name);
  const text = typeof value === "string" ? value : "";
  if (!text.trim()) return parameter.required ? `${label} es obligatorio.` : undefined;
  if (parameter.kind === "integer") {
    return validateNumber(text, label, {
      min: parameter.minimum ?? Number.MIN_SAFE_INTEGER,
      max: parameter.maximum ?? Number.MAX_SAFE_INTEGER,
    });
  }
  return undefined;
}

/*
 * Validación de formato antes de enviar. Da respuesta rápida al administrador; las
 * reglas de verdad las aplica el servidor. La imagen se revisa aparte porque requiere
 * leer el archivo.
 */
export function validateLocationValues(
  values: LocationFormValues,
  effectTypes: LocationEffectType[],
): LocationFormErrors {
  const errors: LocationFormErrors = {};

  const name = values.name.trim();
  if (!name) errors.name = "El nombre es obligatorio.";
  else if (name.length > NAME_MAX_LENGTH) {
    errors.name = `El nombre no puede superar ${NAME_MAX_LENGTH} caracteres.`;
  }

  const description = values.description.trim();
  if (!description) errors.description = "La descripción es obligatoria.";
  else if (description.length > DESCRIPTION_MAX_LENGTH) {
    errors.description = `La descripción no puede superar ${DESCRIPTION_MAX_LENGTH} caracteres.`;
  }

  const cardLimit = validateNumber(
    values.cardLimit,
    "El límite de cartas",
    CARD_LIMIT_RANGE,
  );
  if (cardLimit) errors.cardLimit = cardLimit;

  if (isEnergyMode(values.energyMode)) {
    const amount = validateNumber(values.energyAmount, "La energía extra", {
      min: 0,
      max: MAX_EXTRA_ENERGY[values.energyMode],
    });
    if (amount) errors.energyAmount = amount;
  } else {
    errors.energyMode = "Elige la modalidad de energía extra.";
  }

  const effect = effectTypes.find((type) => type.code === values.effectType);
  for (const parameter of effect?.parameters ?? []) {
    const problem = validateParameter(
      parameter,
      values.effectParameters[parameter.name],
    );
    if (problem) errors[parameterField(parameter.name)] = problem;
  }

  if (!values.image) errors.image = "Adjunta la imagen de la ubicación.";
  return errors;
}

/* Parámetros tal como los espera la API: sin los opcionales vacíos y con sus tipos reales. */
function toEffectParameters(
  effect: LocationEffectType,
  values: Record<string, EffectParameterValue>,
): Record<string, string | number | number[]> {
  const result: Record<string, string | number | number[]> = {};
  for (const parameter of effect.parameters) {
    const value = values[parameter.name];
    if (Array.isArray(value)) {
      if (value.length > 0) result[parameter.name] = value;
    } else if (value?.trim()) {
      result[parameter.name] =
        parameter.kind === "integer" ? Number(value.trim()) : value.trim();
    }
  }
  return result;
}

/* Arma lo que se envía a la API. Solo se llama con valores ya validados. */
export function toCreateLocationInput(
  values: LocationFormValues,
  effectTypes: LocationEffectType[],
): CreateLocationInput {
  if (!values.image) throw new Error("Falta la imagen de la ubicación.");
  if (!isEnergyMode(values.energyMode)) {
    throw new Error("Falta la modalidad de energía extra.");
  }
  const effect = effectTypes.find((type) => type.code === values.effectType);
  return {
    name: values.name.trim(),
    description: values.description.trim(),
    cardLimit: Number(values.cardLimit.trim()),
    energyMode: values.energyMode,
    energyAmount: Number(values.energyAmount.trim()),
    effect: effect
      ? {
          type: effect.code,
          parameters: toEffectParameters(effect, values.effectParameters),
        }
      : null,
    image: values.image,
  };
}

const FIELD_BY_API_NAME: Record<string, LocationFormField> = {
  name: "name",
  description: "description",
  card_limit: "cardLimit",
  extra_energy_mode: "energyMode",
  extra_energy_amount: "energyAmount",
  effect_type: "effectType",
  image: "image",
};

/* Nombre del campo del formulario que corresponde al campo que indica la API. */
export function formFieldFromApi(apiField: string | null): LocationFormField | null {
  if (!apiField) return null;
  const parameter = /^effect_parameters\.(.+)$/.exec(apiField);
  if (parameter) return parameterField(parameter[1]!);
  return FIELD_BY_API_NAME[apiField] ?? null;
}
