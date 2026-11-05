import { forwardRef, type FormEvent } from "react";

import type { References } from "../../api/types";
import { Alert, Button, ImageField, SelectField, TextField } from "../../ui";
import { BackToMenu } from "../BackToMenu";
import {
  COST_RANGE,
  NAME_MAX_LENGTH,
  POWER_RANGE,
  type CardFormErrors,
  type CardFormField,
  type CardFormValues,
} from "./cardRules";
import { CARD_IMAGE } from "./imageRules";

export const FIELD_IDS: Record<CardFormField, string> = {
  name: "card-name",
  cost: "card-cost",
  power: "card-power",
  cardType: "card-type",
  rarity: "card-rarity",
  ability: "card-ability",
  image: "card-image",
};

const FIELD_LABELS: Record<CardFormField, string> = {
  name: "Nombre",
  cost: "Costo",
  power: "Poder",
  cardType: "Tipo",
  rarity: "Rareza",
  ability: "Habilidad",
  image: "Imagen",
};

interface Props {
  references: References;
  values: CardFormValues;
  errors: CardFormErrors;
  /** Error que no pertenece a un campo (sesión, permiso, red...). */
  generalError: string | null;
  submitting: boolean;
  onChange: <K extends CardFormField>(field: K, value: CardFormValues[K]) => void;
  onSubmit: () => void;
}

/** Resumen de errores: recibe el foco al fallar el envío para que se lea primero. */
export const CreateCardForm = forwardRef<HTMLDivElement, Props>(function CreateCardForm(
  { references, values, errors, generalError, submitting, onChange, onSubmit },
  summaryRef,
) {
  const typeName = new Map(references.card_types.map((t) => [t.code, t.name]));
  const errorFields = (Object.keys(FIELD_IDS) as CardFormField[]).filter(
    (field) => errors[field],
  );

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  function focusField(field: CardFormField) {
    document.getElementById(FIELD_IDS[field])?.focus();
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
              : "No se pudo crear la carta"
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
                    onClick={() => focusField(field)}
                  >
                    {FIELD_LABELS[field]}: {errors[field]}
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

      <div className="form__row">
        <TextField
          id={FIELD_IDS.cost}
          label="Costo"
          required
          inputMode="numeric"
          hint={`De ${COST_RANGE.min} a ${COST_RANGE.max}`}
          value={values.cost}
          error={errors.cost}
          disabled={submitting}
          onChange={(value) => onChange("cost", value)}
        />
        <TextField
          id={FIELD_IDS.power}
          label="Poder"
          required
          inputMode="numeric"
          hint={`De ${POWER_RANGE.min} a ${POWER_RANGE.max}. Una carta puede restar poder.`}
          value={values.power}
          error={errors.power}
          disabled={submitting}
          onChange={(value) => onChange("power", value)}
        />
      </div>

      <div className="form__row">
        <SelectField
          id={FIELD_IDS.cardType}
          label="Tipo"
          required
          placeholder="Selecciona un tipo"
          value={values.cardType}
          options={references.card_types.map((t) => ({ value: t.code, label: t.name }))}
          error={errors.cardType}
          disabled={submitting}
          onChange={(value) => onChange("cardType", value)}
        />
        <SelectField
          id={FIELD_IDS.rarity}
          label="Rareza"
          required
          placeholder="Selecciona una rareza"
          value={values.rarity}
          options={references.rarities.map((r) => ({ value: r.code, label: r.name }))}
          error={errors.rarity}
          disabled={submitting}
          onChange={(value) => onChange("rarity", value)}
        />
      </div>

      <SelectField
        id={FIELD_IDS.ability}
        label="Habilidad"
        required
        placeholder="Selecciona una habilidad"
        hint="Es obligatoria. Si la carta no tiene ninguna, elige Sin Habilidad."
        value={values.ability}
        options={references.abilities.map((a) => {
          const affected = a.affected_card_type
            ? ` · afecta a ${typeName.get(a.affected_card_type) ?? a.affected_card_type}`
            : "";
          return { value: a.code, label: `${a.name} (${a.code})${affected}` };
        })}
        error={errors.ability}
        disabled={submitting}
        onChange={(value) => onChange("ability", value)}
      />

      <ImageField
        id={FIELD_IDS.image}
        label="Imagen de la carta"
        required
        accept={CARD_IMAGE.accept}
        hint="PNG, JPG o WebP, hasta 5 MB. Vertical con proporción 5:7 y mínimo 600 × 840 píxeles."
        file={values.image}
        error={errors.image}
        disabled={submitting}
        onChange={(file) => onChange("image", file)}
      />

      <div className="form__actions">
        <Button type="submit" busy={submitting}>
          {submitting ? "Creando carta…" : "Crear carta"}
        </Button>
        <BackToMenu />
      </div>
    </form>
  );
});
