import type { References } from "../../api/types";
import { LocationCard, useObjectUrl } from "../../ui";
import { parseInteger } from "../cards/cardRules";
import type { LocationFormValues } from "./locationRules";

interface Props {
  references: References;
  values: LocationFormValues;
  /* La ubicación ya se creó: se muestra con la animación de revelado. */
  done?: boolean;
}

function signed(amount: number): string {
  return amount < 0 ? `−${Math.abs(amount)}` : `+${amount}`;
}

/* Límite y energía como etiquetas. Lo que aún no es un número válido no se muestra. */
export function describeTags(values: LocationFormValues): string[] {
  const tags: string[] = [];
  const limit = parseInteger(values.cardLimit);
  if (limit !== null) {
    tags.push(limit === 1 ? "Límite: 1 carta" : `Límite: ${limit} cartas`);
  }

  const energy = parseInteger(values.energyAmount);
  if (energy !== null && energy > 0) {
    if (values.energyMode === "fixed") {
      tags.push(`${signed(energy)} energía por jugador`);
    }
    if (values.energyMode === "per_card") {
      tags.push(`${signed(energy)} energía por carta`);
    }
  }
  return tags;
}

/* El efecto en palabras. Un tipo de efecto sin texto propio muestra su nombre del catálogo. */
export function describeEffect(
  values: LocationFormValues,
  references: References,
): string | undefined {
  const effect = references.location_effect_types.find(
    (type) => type.code === values.effectType,
  );
  if (!effect) return undefined;

  const { amount, card_type: cardType, turns } = values.effectParameters;
  const number = typeof amount === "string" ? parseInteger(amount) : null;
  const typeName = references.card_types.find((t) => t.code === cardType)?.name;
  const target = typeName ? `cartas ${typeName}` : "todas las cartas";

  if (effect.code === "type_bonus" && number !== null && typeName) {
    return `${signed(number)} de poder a ${target}`;
  }
  if (effect.code === "cost_modifier" && number !== null) {
    return `${signed(number)} de costo a ${target}`;
  }
  if (effect.code === "turn_restriction" && Array.isArray(turns) && turns.length > 0) {
    return `${effect.name}: ${turns.join(", ")}`;
  }
  return effect.name;
}

/* Muestra la ubicación tal como va quedando mientras se llena el formulario. */
export function LocationPreview({ references, values, done = false }: Props) {
  const imageUrl = useObjectUrl(values.image);

  return (
    <aside
      className={`card-preview${done ? " card-preview--done" : ""}`}
      aria-label="Vista previa"
    >
      <p className="card-preview__title">{done ? "Tu ubicación" : "Vista previa"}</p>
      <LocationCard
        name={values.name.trim() || "Sin nombre"}
        description={values.description.trim()}
        tags={describeTags(values)}
        effect={describeEffect(values, references)}
        imageUrl={imageUrl}
      />
    </aside>
  );
}
