import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useApi } from "../../api/ApiContext";
import type { PlayerDeck } from "../../api/types";
import { Alert, Button, Spinner } from "../../ui";
import { deckErrorMessage } from "./deckRules";

type State =
  | { status: "loading" }
  | { status: "ready"; decks: PlayerDeck[] }
  | { status: "error"; error: unknown };

/* Pantalla Mis decks. */
export function DecksPage() {
  const { decks: api } = useApi();
  const [state, setState] = useState<State>({ status: "loading" });

  const load = useCallback(() => {
    setState({ status: "loading" });
    api.list().then(
      (decks) => setState({ status: "ready", decks }),
      (error: unknown) => setState({ status: "error", error }),
    );
  }, [api]);

  useEffect(load, [load]);

  return (
    <section aria-labelledby="decks-title" className="page">
      <h1 id="decks-title">Mis decks</h1>
      <p className="page__intro">Arma decks de 12 cartas de tu colección.</p>
      <div className="form__actions">
        <Link className="button button--primary" to="/mazos/nuevo">
          Crear deck
        </Link>
      </div>

      <div className="search-area" aria-live="polite">
        {state.status === "loading" && <Spinner label="Cargando tus decks…" />}
        {state.status === "error" && (
          <>
            <Alert variant="error" title="No se pudieron cargar tus decks">
              <p>{deckErrorMessage(state.error)}</p>
            </Alert>
            <Button variant="secondary" onClick={load}>
              Reintentar
            </Button>
          </>
        )}
        {state.status === "ready" && state.decks.length === 0 && (
          <Alert variant="info" title="Aún no tienes decks">
            <p>Crea tu primer deck con 12 cartas de tu colección.</p>
          </Alert>
        )}
        {state.status === "ready" && state.decks.length > 0 && (
          <ul className="deck-list">
            {state.decks.map((deck) => (
              <li key={deck.id}>
                <Link className="deck-list__item" to={`/mazos/${deck.id}`}>
                  <span className="deck-list__name">{deck.name}</span>
                  <span>{deck.cards.length} cartas</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
