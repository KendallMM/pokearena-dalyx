import { useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import type { PlayerCatalogCard } from "../../api/types";
import { GameCard, useObjectUrl } from "../../ui";
import { copiesText } from "./catalogRules";

/*
 * Una carta del catálogo con la marca de cuántas copias tiene el jugador. La imagen
 * (versión grande) pide sesión, así que se descarga cuando la carta se va a ver.
 */
export function CatalogCardItem({ card }: { card: PlayerCatalogCard }) {
  const { playerCatalog } = useApi();
  const element = useRef<HTMLLIElement>(null);
  const [visible, setVisible] = useState(false);
  const [image, setImage] = useState<Blob | null>(null);
  const [failed, setFailed] = useState(false);
  const imageUrl = useObjectUrl(image);

  useEffect(() => {
    if (!element.current || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setVisible(true);
      },
      { rootMargin: "200px" },
    );
    observer.observe(element.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    playerCatalog.image(card.image_url).then(
      (blob) => {
        if (!cancelled) setImage(blob);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [visible, playerCatalog, card.image_url]);

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
        imageHint={failed ? "No se pudo cargar la imagen" : "Cargando imagen…"}
      />
      <p
        className={`catalog-card__copies${card.owned ? " catalog-card__copies--owned" : ""}`}
      >
        {copiesText(card.copies)}
      </p>
    </li>
  );
}
