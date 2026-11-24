import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { useApi } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { MatchSearch } from "../api/searches";
import { Alert, Spinner } from "../ui";

export function AssignedMatchPage() {
  const { matchId } = useParams();
  const { state } = useLocation();
  const { searches } = useApi();
  const [search, setSearch] = useState<MatchSearch | null>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    let active = true;
    searches.current().then(
      (result) => {
        if (active) setSearch(result.match_id === matchId ? result : null);
      },
      (failure: unknown) => {
        if (!active) return;
        if (failure instanceof ApiError && failure.status !== 404) {
          setError(failure.message);
        } else {
          setSearch(null);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [matchId, searches]);

  return (
    <section className="page" aria-labelledby="assigned-title">
      <h1 id="assigned-title">Partida asignada</h1>
      {error && <Alert variant="error" title={error} />}
      {search === undefined && !error && <Spinner label="Cargando partida…" />}
      {search === null && (
        <Alert variant="error" title="La partida no está disponible." />
      )}
      {search &&
        typeof state?.matchNotice?.title === "string" &&
        typeof state.matchNotice.message === "string" && (
          <Alert variant="info" title={state.matchNotice.title}>
            <p>{state.matchNotice.message}</p>
          </Alert>
        )}
      {search && (
        <Alert variant="success" title={`Partida encontrada: ${search.match_id}`}>
          <p>La preparación del tablero todavía no está disponible.</p>
        </Alert>
      )}
      <Link className="button button--secondary" to="/mazos">
        Mis decks
      </Link>
    </section>
  );
}
