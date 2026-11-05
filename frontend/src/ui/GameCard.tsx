import type { PointerEvent } from "react";

interface Props {
  name: string;
  cost: number | string;
  power: number | string;
  /* Código del tipo (FUE, AGU...): define el color de la carta. */
  typeCode?: string;
  typeName?: string;
  /* Código de la rareza (COMMON, RARE...): define el marco de la carta. */
  rarityCode?: string;
  rarityName?: string;
  abilityName?: string;
  imageUrl?: string | null;
}

const MAX_TILT_DEGREES = 12;

function tiltTowardsPointer(event: PointerEvent<HTMLElement>) {
  const card = event.currentTarget;
  const box = card.getBoundingClientRect();
  const x = (event.clientX - box.left) / box.width;
  const y = (event.clientY - box.top) / box.height;
  card.style.setProperty("--tilt-x", `${(0.5 - y) * MAX_TILT_DEGREES}deg`);
  card.style.setProperty("--tilt-y", `${(x - 0.5) * MAX_TILT_DEGREES}deg`);
}

function resetTilt(event: PointerEvent<HTMLElement>) {
  event.currentTarget.style.removeProperty("--tilt-x");
  event.currentTarget.style.removeProperty("--tilt-y");
}

/* Carta del juego. Solo muestra lo que recibe; no conoce la API. */
export function GameCard({
  name,
  cost,
  power,
  typeCode,
  typeName,
  rarityCode,
  rarityName,
  abilityName,
  imageUrl,
}: Props) {
  const negative = typeof power === "number" && power < 0;

  return (
    <article
      className="game-card"
      data-type={typeCode || undefined}
      data-rarity={rarityCode || undefined}
      onPointerMove={tiltTowardsPointer}
      onPointerLeave={resetTilt}
    >
      <div className="game-card__inner">
        <div className="game-card__top">
          <div className="game-card__stat game-card__stat--cost">
            <span>
              <span className="visually-hidden">Costo: </span>
              {cost}
            </span>
          </div>
          <h2 className="game-card__name">{name}</h2>
          <div
            className={`game-card__stat game-card__stat--power${
              negative ? " game-card__stat--negative" : ""
            }`}
          >
            <span>
              <span className="visually-hidden">Poder: </span>
              {power}
            </span>
          </div>
        </div>
        <div className="game-card__picture">
          {imageUrl ? (
            <img className="game-card__art" src={imageUrl} alt="" />
          ) : (
            <div className="game-card__empty">Aquí se verá la imagen</div>
          )}
        </div>
        <div className="game-card__panel">
          {(typeName || rarityName) && (
            <div className="game-card__tags">
              {typeName && (
                <span className="game-card__tag game-card__tag--type">{typeName}</span>
              )}
              {rarityName && <span className="game-card__tag">{rarityName}</span>}
            </div>
          )}
          {abilityName && <p className="game-card__ability-name">{abilityName}</p>}
        </div>
      </div>
    </article>
  );
}
