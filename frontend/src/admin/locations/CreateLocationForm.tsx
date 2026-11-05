import { forwardRef, type FormEvent } from "react";

import type { EffectParameter, EnergyMode, References } from "../../api/types";
import {
  Alert,
  Button,
  CheckboxGroupField,
  ImageField,
  SelectField,
  TextAreaField,
  TextField,
} from "../../ui";
import { LOCATION_IMAGE } from "./locationImageRules";
import {
  CARD_LIMIT_RANGE,
  DESCRIPTION_MAX_LENGTH,
  ENERGY_MODE_LABELS,
  MAX_EXTRA_ENERGY,
  NAME_MAX_LENGTH,
  parameterField,
  parameterLabel,
  type EffectParameterValue,
  type LocationFormErrors,
  type LocationFormField,
  type LocationFormValues,
  type LocationValueField,
} from "./locationRules";

const FIELD_IDS: Record<LocationValueField, string> = {
  name: "location-name",
  description: "location-description",
  cardLimit: "location-card-limit",
  energyMode: "location-energy-mode",
  energyAmount: "location-energy-amount",
  effectType: "location-effect-type",
  image: "location-image",
};

const FIELD_LABELS: Record<LocationValueField, string> = {
  name: "Nombre",
  description: "Descripción",
  cardLimit: "Límite de cartas",
  energyMode: "Modalidad de energía extra",
  energyAmount: "Energía extra",
  effectType: "Efecto",
  image: "Imagen",
};

const PARAMETER_PREFIX = "parameter:";

function parameterId(name: string): string {
  return `location-parameter-${name}`;
}

function fieldId(field: LocationFormField): string {
  return field.startsWith(PARAMETER_PREFIX)
    ? parameterId(field.slice(PARAMETER_PREFIX.length))
    : FIELD_IDS[field as LocationValueField];
}

function fieldLabel(field: LocationFormField): string {
  return field.startsWith(PARAMETER_PREFIX)
    ? parameterLabel(field.slice(PARAMETER_PREFIX.length))
    : FIELD_LABELS[field as LocationValueField];
}

function rangeOf(parameter: EffectParameter): number[] {
  const { minimum: low, maximum: high } = parameter;
  if (low === null || high === null) return [];
  return Array.from({ length: high - low + 1 }, (_, index) => low + index);
}

interface Props {
  references: References;
  values: LocationFormValues;
  errors: LocationFormErrors;
  /* Error que no pertenece a un campo (sesión, permiso, red...). */
  generalError: string | null;
  submitting: boolean;
  onChange: <K extends LocationValueField>(
    field: K,
    value: LocationFormValues[K],
  ) => void;
  onParameterChange: (name: string, value: EffectParameterValue) => void;
  onSubmit: () => void;
}

/* Resumen de errores: recibe el foco al fallar el envío para que se lea primero. */
export const CreateLocationForm = forwardRef<HTMLDivElement, Props>(
  function CreateLocationForm(
    {
      references,
      values,
      errors,
      generalError,
      submitting,
      onChange,
      onParameterChange,
      onSubmit,
    },
    summaryRef,
  ) {
    const errorFields = Object.keys(errors).filter(
      (field) => errors[field as LocationFormField],
    ) as LocationFormField[];
    const effect = references.location_effect_types.find(
      (type) => type.code === values.effectType,
    );
    const energyMax =
      values.energyMode in MAX_EXTRA_ENERGY
        ? MAX_EXTRA_ENERGY[values.energyMode as EnergyMode]
        : null;

    function handleSubmit(event: FormEvent) {
      event.preventDefault();
      onSubmit();
    }

    function renderParameter(parameter: EffectParameter) {
      const id = parameterId(parameter.name);
      const label = parameterLabel(parameter.name);
      const error = errors[parameterField(parameter.name)];
      const value = values.effectParameters[parameter.name];

      if (parameter.kind === "integer_list") {
        return (
          <CheckboxGroupField
            key={parameter.name}
            id={id}
            label={label}
            required={parameter.required}
            hint="Elige en cuáles turnos aplica."
            options={rangeOf(parameter)}
            selected={Array.isArray(value) ? value : []}
            error={error}
            disabled={submitting}
            onChange={(selected) => onParameterChange(parameter.name, selected)}
          />
        );
      }
      const text = typeof value === "string" ? value : "";
      if (parameter.kind === "card_type") {
        return (
          <SelectField
            key={parameter.name}
            id={id}
            label={label}
            required={parameter.required}
            placeholder={parameter.required ? "Selecciona un tipo" : "Todos los tipos"}
            value={text}
            options={references.card_types.map((t) => ({
              value: t.code,
              label: t.name,
            }))}
            error={error}
            disabled={submitting}
            onChange={(next) => onParameterChange(parameter.name, next)}
          />
        );
      }
      return (
        <TextField
          key={parameter.name}
          id={id}
          label={label}
          required={parameter.required}
          inputMode="numeric"
          hint={`De ${parameter.minimum} a ${parameter.maximum}`}
          value={text}
          error={error}
          disabled={submitting}
          onChange={(next) => onParameterChange(parameter.name, next)}
        />
      );
    }

    return (
      <form className="form" onSubmit={handleSubmit} noValidate>
        {(errorFields.length > 0 || generalError) && (
          <Alert
            ref={summaryRef}
            variant="error"
            title={
              errorFields.length > 0
                ? "Revisa estos datos antes de continuar"
                : "No se pudo crear la ubicación"
            }
          >
            {generalError && <p>{generalError}</p>}
            {errorFields.length > 0 && (
              <ul className="error-list">
                {errorFields.map((field) => (
                  <li key={field}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => document.getElementById(fieldId(field))?.focus()}
                    >
                      {fieldLabel(field)}: {errors[field]}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Alert>
        )}

        <TextField
          id={FIELD_IDS.name}
          label="Nombre"
          required
          value={values.name}
          maxLength={NAME_MAX_LENGTH}
          error={errors.name}
          disabled={submitting}
          onChange={(value) => onChange("name", value)}
        />

        <TextAreaField
          id={FIELD_IDS.description}
          label="Descripción"
          required
          value={values.description}
          maxLength={DESCRIPTION_MAX_LENGTH}
          error={errors.description}
          disabled={submitting}
          onChange={(value) => onChange("description", value)}
        />

        <TextField
          id={FIELD_IDS.cardLimit}
          label="Límite de cartas"
          required
          inputMode="numeric"
          hint={`Por jugador, de ${CARD_LIMIT_RANGE.min} a ${CARD_LIMIT_RANGE.max}. Con 0 no se pueden jugar cartas aquí.`}
          value={values.cardLimit}
          error={errors.cardLimit}
          disabled={submitting}
          onChange={(value) => onChange("cardLimit", value)}
        />

        <div className="form__row">
          <SelectField
            id={FIELD_IDS.energyMode}
            label="Modalidad de energía extra"
            required
            placeholder="Selecciona una modalidad"
            value={values.energyMode}
            options={(Object.keys(ENERGY_MODE_LABELS) as EnergyMode[]).map((mode) => ({
              value: mode,
              label: ENERGY_MODE_LABELS[mode],
            }))}
            error={errors.energyMode}
            disabled={submitting}
            onChange={(value) => onChange("energyMode", value)}
          />
          <TextField
            id={FIELD_IDS.energyAmount}
            label="Energía extra"
            required
            inputMode="numeric"
            hint={
              energyMax === null
                ? "Primero elige la modalidad."
                : `De 0 a ${energyMax}. Con 0 no da energía.`
            }
            value={values.energyAmount}
            error={errors.energyAmount}
            disabled={submitting}
            onChange={(value) => onChange("energyAmount", value)}
          />
        </div>

        <SelectField
          id={FIELD_IDS.effectType}
          label="Efecto"
          placeholder="Sin efecto"
          hint="Es opcional."
          value={values.effectType}
          options={references.location_effect_types.map((type) => ({
            value: type.code,
            label: type.name,
          }))}
          error={errors.effectType}
          disabled={submitting}
          onChange={(value) => onChange("effectType", value)}
        />

        {effect && effect.parameters.length > 0 && (
          <div className="form__row">{effect.parameters.map(renderParameter)}</div>
        )}

        <ImageField
          id={FIELD_IDS.image}
          label="Imagen de la ubicación"
          required
          accept={LOCATION_IMAGE.accept}
          hint="PNG, JPG o WebP, hasta 5 MB. Horizontal con proporción 4:3 y mínimo 800 × 600 píxeles."
          file={values.image}
          error={errors.image}
          disabled={submitting}
          onChange={(file) => onChange("image", file)}
        />

        <div className="form__actions">
          <Button type="submit" busy={submitting}>
            {submitting ? "Creando ubicación…" : "Crear ubicación"}
          </Button>
        </div>
      </form>
    );
  },
);
