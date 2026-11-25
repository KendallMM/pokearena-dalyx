import { useEffect, useState } from "react";

import { BackToMenu } from "../admin/BackToMenu";
import { useApi } from "../api/ApiContext";
import { useLazyCardImage } from "../player/catalog/useLazyCardImage";
import { GameCard, useObjectUrl } from "../ui";
import {
  EXAMPLE_MATCH,
  formatTime,
  leaderOf,
  timeLeftPercent,
  totalPower,
  type HandCard,
  type Leader,
  type MatchLocation,
  type MatchView,
} from "./match";

const LEADER_TEXT: Record<Leader, string> = {
  player: "Vas ganando",
  rival: "Va ganando el rival",
  tie: "Empate",
};

function PlayedCards({
  owner,
  powers,
}: {
  owner: "rival" | "player";
  powers: number[];
}) {
  return (
    <ul className={`match-played match-played--${owner}`}>
      {powers.map((power, index) => (
        <li key={index} className="match-played__card">
          <span className="visually-hidden">Carta de poder </span>
          {power}
        </li>
      ))}
      {powers.length === 0 && (
        <li className="match-played__empty">
          <span aria-hidden="true">—</span>
          <span className="visually-hidden">Sin cartas</span>
        </li>
      )}
    </ul>
  );
}

function LocationPreview({ matchId, locationId }: { matchId: string; locationId: number }) {
  const { matches } = useApi();
  const [image, setImage] = useState<Blob | null>(null);
  const imageUrl = useObjectUrl(image);

  useEffect(() => {
    let active = true;
    matches.locationImage(matchId, locationId).then(
      (blob) => {
        if (active) setImage(blob);
      },
      () => {},
    );
    return () => {
      active = false;
    };
  }, [matches, matchId, locationId]);

  return imageUrl && <img className="match-location__image" src={imageUrl} alt="" />;
}

function LocationColumn({ location }: { location: MatchLocation }) {
  const rivalPower = totalPower(location.rivalCards);
  const playerPower = totalPower(location.playerCards);
  const leader = leaderOf(rivalPower, playerPower);

  return (
    <section className="match-column" data-leader={leader} aria-label={location.name}>
      <PlayedCards owner="rival" powers={location.rivalCards} />
      <p className="match-power match-power--rival">
        <span className="visually-hidden">Rival: </span>
        {rivalPower}
      </p>
      <div className="match-location">
        <h2 className="match-location__name">{location.name}</h2>
        {location.imageMatchId && location.id !== undefined && (
          <LocationPreview matchId={location.imageMatchId} locationId={location.id} />
        )}
        <p className="match-location__effect">{location.effect}</p>
        <p className="visually-hidden">{LEADER_TEXT[leader]}</p>
      </div>
      <p className="match-power match-power--player">
        <span className="visually-hidden">Tú: </span>
        {playerPower}
      </p>
      <PlayedCards owner="player" powers={location.playerCards} />
    </section>
  );
}

function IllustratedHandCard({ card, code }: { card: HandCard; code: string }) {
  const { element, imageUrl, imageHint } = useLazyCardImage<HTMLLIElement>(
    `/v1/cartas/${encodeURIComponent(code)}/imagen`,
  );

  return (
    <li ref={element} className="match-hand__illustrated">
      <GameCard
        name={card.name}
        cost={card.cost}
        power={card.power ?? "?"}
        typeCode={card.type ?? undefined}
        typeName={card.type_name ?? undefined}
        rarityCode={card.rarity ?? undefined}
        rarityName={card.rarity_name ?? undefined}
        abilityName={card.ability_name ?? undefined}
        imageUrl={imageUrl}
        imageHint={imageHint}
      />
    </li>
  );
}

function HandCardView({ card, energy }: { card: HandCard; energy: number }) {
  if (card.code) return <IllustratedHandCard card={card} code={card.code} />;
  const playable = card.cost <= energy;
  return (
    <li className={`match-card${playable ? "" : " match-card--unplayable"}`}>
      <span className="match-card__cost">
        <span className="visually-hidden">Costo: </span>
        {card.cost}
      </span>
      <span className="match-card__power">
        <span className="visually-hidden">Poder: </span>
        {card.power ?? "?"}
      </span>
      <span className="match-card__name">{card.name}</span>
      {!playable && <span className="visually-hidden">No alcanza la energía</span>}
    </li>
  );
}

/* La vista inicial comparte el tablero y omite las acciones de turno. */
export function MatchPage({
  match = EXAMPLE_MATCH,
  initial = false,
}: {
  match?: MatchView;
  initial?: boolean;
}) {
  const Board = initial ? "div" : "main";
  return (
    <Board className="match">
      {!initial && <h1 className="visually-hidden">Partida</h1>}

      <header className="match-top">
        <p className="match-top__rival">
          <strong>{match.rival.name}</strong>
          {match.rival.elo !== undefined && <> Elo {match.rival.elo}</>}
        </p>
        {match.rival.confirmed && <p>Ya confirmó</p>}
        {match.betCubes !== null && <p>Apuesta: {match.betCubes} cubos</p>}
        {!initial && <BackToMenu />}
      </header>

      <div className="match-board">
        {match.locations.map((location) => (
          <LocationColumn key={location.id ?? location.name} location={location} />
        ))}
      </div>

      <ul className="match-hand" aria-label="Tu mano">
        {match.hand.map((card, index) => (
          <HandCardView key={card.code ?? index} card={card} energy={match.energy} />
        ))}
      </ul>

      <div className="match-actions">
        <dl className="match-stats">
          <div>
            <dt>Turno</dt>
            <dd>
              {match.turn}/{match.totalTurns}
            </dd>
          </div>
          <div>
            <dt>Energía</dt>
            <dd className="match-stats__energy">{match.energy}</dd>
          </div>
          <div>
            <dt>Tiempo</dt>
            <dd className="match-stats__time">
              {formatTime(match.secondsLeft)}
              <span className="match-time-bar" aria-hidden="true">
                <span
                  className="match-time-bar__left"
                  style={{
                    width: `${timeLeftPercent(match.secondsLeft, match.turnSeconds)}%`,
                  }}
                />
              </span>
            </dd>
          </div>
        </dl>
        {!initial && (
          <div className="match-actions__group">
            <button type="button" className="match-button">
              Dynamax
            </button>
            <button type="button" className="match-button">
              Run
            </button>
            <button type="button" className="match-button match-button--confirm">
              Confirmar
            </button>
          </div>
        )}
      </div>
    </Board>
  );
}
