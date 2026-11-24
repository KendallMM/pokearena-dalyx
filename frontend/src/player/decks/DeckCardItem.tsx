import type { DeckCard } from "../../api/types";
import { GameCard } from "../../ui";
import { useLazyCardImage } from "../catalog/useLazyCardImage";

interface Props {
  card: DeckCard;
  /* Al crear un deck, la carta se puede marcar. */
  selection?: { selected: boolean; disabled: boolean; onToggle: () => void };
}

/* Una carta de un deck, o de la colección mientras se arma uno. */
export function DeckCardItem({ card, selection }: Props) {
  const { element, imageUrl, imageHint } = useLazyCardImage<HTMLLIElement>(
    card.image_url,
  );

  return (
    <li
      ref={element}
      className={`search-result${selection?.selected ? " deck-card--selected" : ""}`}
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
      {selection && (
        <label className="catalog-owned-toggle deck-card__pick">
          <input
            type="checkbox"
            checked={selection.selected}
            disabled={selection.disabled}
            onChange={selection.onToggle}
            aria-label={`Elegir ${card.name}`}
          />
          {selection.selected ? "En el deck" : "Elegir"}
        </label>
      )}
    </li>
  );
}
