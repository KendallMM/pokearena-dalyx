import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { useApi } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { InitialMatch } from "../api/matches";
import { Alert, Spinner } from "../ui";
import { MatchPage } from "./MatchPage";

function InitialBoard({
  match,
  receivedAt,
}: {
  match: InitialMatch;
  receivedAt: number;
}) {
  const [now, setNow] = useState(receivedAt);
  // Descuenta el tiempo transcurrido desde la respuesta con un reloj monotónico.
  // Llegar a cero solo actualiza la pantalla.
  const remaining = Math.max(0, match.remaining_ms - (now - receivedAt));
  useEffect(() => {
    if (remaining === 0) return;
    const timer = window.setTimeout(
      () => setNow(performance.now()),
      Math.min(1000, remaining),
    );
    return () => window.clearTimeout(timer);
  }, [remaining]);
  return (
    <MatchPage
      initial
      match={{
        rival: { name: match.mode === "bot" ? "Bot" : "Rival", confirmed: false },
        betCubes: match.stake,
        turn: match.turn,
        totalTurns: match.total_turns,
        energy: match.energy,
        secondsLeft: Math.ceil(remaining / 1000),
        turnSeconds: match.turn_seconds,
        locations: match.locations.map((location) => ({
          id: location.id,
          imageMatchId: location.has_image ? match.id : undefined,
          name: location.name,
          effect: location.description,
          playerCards: [],
          rivalCards: [],
        })),
        hand: match.hand,
      }}
    />
  );
}

export function AssignedMatchPage() {
  const { matchId } = useParams();
  const { state } = useLocation();
  const { matches } = useApi();
  const [loaded, setLoaded] = useState<{ match: InitialMatch; receivedAt: number }>();
  const [failure, setFailure] = useState<{ id: string; message: string }>();
  const current = loaded?.match.id === matchId ? loaded : undefined;
  const error = failure?.id === matchId ? failure?.message : undefined;

  useEffect(() => {
    if (!matchId) return;
    let active = true;
    matches.initial(matchId).then(
      (match) => {
        if (active) setLoaded({ match, receivedAt: performance.now() });
      },
      (cause: unknown) => {
        if (active)
          setFailure({
            id: matchId,
            message:
              cause instanceof ApiError
                ? cause.message
                : "No se pudo consultar la partida.",
          });
      },
    );
    return () => {
      active = false;
    };
  }, [matchId, matches]);

  return (
    <section className="page" aria-labelledby="assigned-title">
      <h1 id="assigned-title">Partida asignada</h1>
      {error && <Alert variant="error" title={error} />}
      {!current && !error && <Spinner label="Cargando partida…" />}
      {current &&
        typeof state?.matchNotice?.title === "string" &&
        typeof state.matchNotice.message === "string" && (
          <Alert variant="info" title={state.matchNotice.title}>
            <p>{state.matchNotice.message}</p>
          </Alert>
        )}
      {current && (
        <>
          <Alert variant="success" title={`Partida encontrada: ${current.match.id}`} />
          <InitialBoard key={current.match.id} {...current} />
        </>
      )}
      {error && (
        <Link className="button button--secondary" to="/mazos">
          Mis decks
        </Link>
      )}
    </section>
  );
}
