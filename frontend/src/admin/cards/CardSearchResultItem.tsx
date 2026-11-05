import { useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import type { CardSearchResult } from "../../api/types";
import { GameCard, useObjectUrl } from "../../ui";

function imageStatusText({
  image_status,
  thumbnail_attempts,
}: CardSearchResult): string {
  if (image_status === "available") return "Imagen disponible";
  return thumbnail_attempts > 0
    ? `Imagen en proceso (${thumbnail_attempts} intentos fallidos)`
    : "Imagen en proceso";
}

/*
 * Una carta del resultado. La imagen pide sesión, así que se descarga con el cliente de
 * la API; y como solo existe la versión grande, se pide cuando la carta se va a ver.
 */
export function CardSearchResultItem({ card }: { card: CardSearchResult }) {
  const { cards } = useApi();
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
    cards.image(card.image_url).then(
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
  }, [visible, cards, card.image_url]);

  return (
    <li ref={element} className="search-result">
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
      <p className="search-result__code">{card.code}</p>
      <p className="search-result__status">{imageStatusText(card)}</p>
      {imageUrl && (
        <a
          className="search-result__link"
          href={imageUrl}
          target="_blank"
          rel="noreferrer"
        >
          Ver imagen completa
        </a>
      )}
    </li>
  );
}
