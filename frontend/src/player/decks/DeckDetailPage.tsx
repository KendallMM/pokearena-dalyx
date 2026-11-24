import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useApi } from "../../api/ApiContext";
import type { PlayerDeck } from "../../api/types";
import { Alert, Spinner } from "../../ui";
import { DeckCardItem } from "./DeckCardItem";
import { deckErrorMessage } from "./deckRules";

type State =
  | { status: "loading" }
  | { status: "ready"; deck: PlayerDeck }
  | { status: "error"; error: unknown };

/* Un deck del jugador con sus cartas. */
export function DeckDetailPage() {
  const { deckId = "" } = useParams();
  const { decks } = useApi();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    decks.get(deckId).then(
      (deck) => {
        if (!cancelled) setState({ status: "ready", deck });
      },
      (error: unknown) => {
        if (!cancelled) setState({ status: "error", error });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [decks, deckId]);

  return (
    <section aria-labelledby="deck-title" className="page">
      <h1 id="deck-title">{state.status === "ready" ? state.deck.name : "Deck"}</h1>
      <div className="form__actions">
        <Link className="button button--secondary" to="/mazos">
          Volver a mis decks
        </Link>
      </div>
      <div className="search-area" aria-live="polite">
        {state.status === "loading" && <Spinner label="Cargando el deck…" />}
        {state.status === "error" && (
          <Alert variant="error" title="No se pudo abrir el deck">
            <p>{deckErrorMessage(state.error)}</p>
          </Alert>
        )}
        {state.status === "ready" && (
          <ul className="search-results">
            {state.deck.cards.map((card) => (
              <DeckCardItem key={card.code} card={card} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
