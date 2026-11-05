/* Datos que necesita la pantalla de partida. */
export interface MatchLocation {
  name: string;
  effect: string;
  /* Poder de cada carta jugada en esta ubicación. */
  rivalCards: number[];
  playerCards: number[];
}

export interface HandCard {
  name: string;
  cost: number;
  /* null mientras no exista el dato real de la carta. */
  power: number | null;
}

export interface MatchView {
  rival: { name: string; elo: number; confirmed: boolean };
  betCubes: number;
  turn: number;
  totalTurns: number;
  energy: number;
  secondsLeft: number;
  /* Duración completa del turno, para dibujar la barra de tiempo. */
  turnSeconds: number;
  locations: MatchLocation[];
  hand: HandCard[];
}

export type Leader = "player" | "rival" | "tie";

export function totalPower(cards: number[]): number {
  return cards.reduce((sum, power) => sum + power, 0);
}

/* Quién va ganando una ubicación según el poder de cada lado. */
export function leaderOf(rivalPower: number, playerPower: number): Leader {
  if (playerPower > rivalPower) return "player";
  if (rivalPower > playerPower) return "rival";
  return "tie";
}

/* Convierte segundos al formato del temporizador, por ejemplo 0:18. */
export function formatTime(seconds: number): string {
  const rest = String(seconds % 60).padStart(2, "0");
  return `${Math.floor(seconds / 60)}:${rest}`;
}

/* Porcentaje del turno que queda, siempre entre 0 y 100. */
export function timeLeftPercent(secondsLeft: number, turnSeconds: number): number {
  return Math.min(100, Math.max(0, (secondsLeft / turnSeconds) * 100));
}

/* Partida de ejemplo: no hay API de partidas todavía. */
export const EXAMPLE_MATCH: MatchView = {
  rival: { name: "[Rival]", elo: 1240, confirmed: true },
  betCubes: 4,
  turn: 3,
  totalTurns: 6,
  energy: 6,
  secondsLeft: 18,
  turnSeconds: 30,
  locations: [
    {
      name: "Ubicación 1",
      effect: "+2 de poder a cartas Agua",
      rivalCards: [1, 2],
      playerCards: [9],
    },
    {
      name: "Ubicación 2",
      effect: "Bloqueada hasta el turno 4",
      rivalCards: [],
      playerCards: [],
    },
    {
      name: "Ubicación 3",
      effect: "−1 de costo a cartas Fuego",
      rivalCards: [5, 6],
      playerCards: [4],
    },
  ],
  hand: [
    { name: "[Carta]", cost: 0, power: null },
    { name: "[Carta]", cost: 2, power: null },
    { name: "[Carta]", cost: 4, power: null },
    { name: "[Carta]", cost: 7, power: null },
  ],
};
