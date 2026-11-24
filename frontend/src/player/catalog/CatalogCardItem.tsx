import type { PlayerCatalogCard } from "../../api/types";
import { GameCard } from "../../ui";
import { copiesText } from "./catalogRules";
import { useLazyCardImage } from "./useLazyCardImage";

/* Una carta del catálogo con la marca de cuántas copias tiene el jugador. */
export function CatalogCardItem({ card }: { card: PlayerCatalogCard }) {
  const { element, imageUrl, imageHint } = useLazyCardImage<HTMLLIElement>(
    card.image_url,
  );

  return (
    <li
      ref={element}
      className={`search-result catalog-card${card.owned ? "" : " catalog-card--missing"}`}
    >
      <GameCard
        name={card.name}
        cost={card.cost}
        power={card.power}
        typeCode={card.card_type.code}
        typeName={card.card_type.name}
        rarityCode={card.rarity.code}
        rarityName={card.rarity.name}
        abilityName={card.ability.name}
        imageUrl={imageUrl}
        imageHint={imageHint}
      />
      <p
        className={`catalog-card__copies${card.owned ? " catalog-card__copies--owned" : ""}`}
      >
        {copiesText(card.copies)}
      </p>
    </li>
  );
}
