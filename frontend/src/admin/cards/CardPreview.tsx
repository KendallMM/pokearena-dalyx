import type { References } from "../../api/types";
import { GameCard, useObjectUrl } from "../../ui";
import { parseInteger, type CardFormValues } from "./cardRules";

interface Props {
  references: References;
  values: CardFormValues;
  /* La carta ya se creó: se muestra con la animación de revelado. */
  done?: boolean;
}

/* Muestra la carta tal como va quedando mientras se llena el formulario. */
export function CardPreview({ references, values, done = false }: Props) {
  const imageUrl = useObjectUrl(values.image);
  const typeName = references.card_types.find((t) => t.code === values.cardType)?.name;
  const rarityName = references.rarities.find((r) => r.code === values.rarity)?.name;
  const abilityName = references.abilities.find((a) => a.code === values.ability)?.name;

  return (
    <aside
      className={`card-preview${done ? " card-preview--done" : ""}`}
      aria-label="Vista previa"
    >
      <p className="card-preview__title">{done ? "Tu carta" : "Vista previa"}</p>
      <GameCard
        name={values.name.trim() || "Sin nombre"}
        cost={parseInteger(values.cost) ?? "?"}
        power={parseInteger(values.power) ?? "?"}
        typeCode={values.cardType}
        typeName={typeName}
        rarityCode={values.rarity}
        rarityName={rarityName}
        abilityName={abilityName}
        imageUrl={imageUrl}
      />
    </aside>
  );
}
