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

function HandCardView({ card, energy }: { card: HandCard; energy: number }) {
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

/* Pantalla de partida. Por ahora es solo el diseño: los botones aún no hacen nada. */
export function MatchPage({ match = EXAMPLE_MATCH }: { match?: MatchView }) {
  return (
    <main className="match">
      <h1 className="visually-hidden">Partida</h1>

      <header className="match-top">
        <p className="match-top__rival">
          <strong>{match.rival.name}</strong> Elo {match.rival.elo}
        </p>
        {match.rival.confirmed && <p>Ya confirmó</p>}
        <p>Apuesta: {match.betCubes} cubos</p>
      </header>

      <div className="match-board">
        {match.locations.map((location) => (
          <LocationColumn key={location.name} location={location} />
        ))}
      </div>

      <ul className="match-hand" aria-label="Tu mano">
        {match.hand.map((card, index) => (
          <HandCardView key={index} card={card} energy={match.energy} />
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
      </div>
    </main>
  );
}
