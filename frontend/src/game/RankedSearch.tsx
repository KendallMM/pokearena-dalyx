import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useOperationKey } from "../admin/cards/operationId";
import { useApi } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { MatchSearch } from "../api/searches";
import type { PlayerDeck } from "../api/types";
import { Alert, Button, SelectField, Spinner } from "../ui";

export function RankedSearch({ collectionMessage }: { collectionMessage?: string }) {
  const { decks, searches } = useApi();
  const [available, setAvailable] = useState<PlayerDeck[]>([]);
  const [search, setSearch] = useState<MatchSearch | null>(null);
  const [deckId, setDeckId] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const operation = useOperationKey();
  const submitting = useRef(false);
  const waiting = search?.status === "waiting" || search?.status === "reserved";
  const found = search?.status === "found";

  useEffect(() => {
    let active = true;
    Promise.all([decks.list(), searches.current()]).then(
      ([items, current]) => {
        if (!active) return;
        setAvailable(items);
        setSearch(current);
        setDeckId(current?.deck_id ?? "");
        setReady(true);
      },
      (failure: Error) => {
        if (active) setError(failure);
      },
    );
    return () => {
      active = false;
    };
  }, [decks, searches, reload]);

  const waitingId = waiting ? search.id : null;
  // Consulta el estado solo mientras la búsqueda está abierta.
  useEffect(() => {
    if (!waitingId || busy) return;
    const id = waitingId;
    let active = true;
    let timer: number;
    async function poll() {
      try {
        const next = await searches.get(id);
        if (!active) return;
        setSearch(next);
        setError(null);
        if (next.status === "waiting" || next.status === "reserved") {
          timer = window.setTimeout(poll, 2000);
        }
      } catch (failure) {
        if (!active) return;
        setError(failure as Error);
        if (
          !(failure instanceof ApiError) ||
          ![401, 403, 404].includes(failure.status)
        ) {
          timer = window.setTimeout(poll, 2000);
        }
      }
    }
    timer = window.setTimeout(poll, 2000);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [waitingId, busy, searches]);

  async function run(action: () => Promise<MatchSearch>) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      const next = await action();
      setSearch(next);
      operation.reset();
    } catch (failure) {
      setError(failure as Error);
      if (failure instanceof ApiError && failure.status === 409) {
        try {
          const current = await searches.current();
          if (current) setSearch(current);
        } catch {
          // Conserva el mensaje de la operación original.
        }
      }
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function enter() {
    if (!deckId) {
      setError(new Error("Selecciona un deck para buscar partida."));
      return;
    }
    const key = operation.current();
    void run(() => searches.enter(deckId, key));
  }

  return (
    <section className="page" aria-labelledby="ranked-title">
      <h1 id="ranked-title">Partida clasificatoria</h1>
      <p className="page__intro">
        Elige un deck para buscar un rival de nivel similar.
      </p>
      {collectionMessage && (
        <Alert variant="info" title="Colección inicial">
          <p>{collectionMessage}</p>
        </Alert>
      )}
      {error && (
        <Alert variant="error" title="No se pudo completar la solicitud">
          <p>{error.message}</p>
          {error instanceof ApiError && error.isNotAuthenticated && (
            <Link to="/login">Iniciar sesión</Link>
          )}
          {!ready && (
            <Button
              onClick={() => {
                setError(null);
                setReload((value) => value + 1);
              }}
            >
              Reintentar
            </Button>
          )}
        </Alert>
      )}
      {!ready && !error && <Spinner label="Cargando tus decks y tu búsqueda…" />}
      {ready &&
        (waiting || found ? (
          <div className="form search-form">
            {waiting ? (
              <Spinner label="Buscando rival" />
            ) : (
              <Alert
                variant="success"
                title={`Partida encontrada: ${search.match_id}`}
              />
            )}
            <p>
              Deck:{" "}
              {available.find((deck) => deck.id === search.deck_id)?.name ??
                search.deck_id}
            </p>
            {search.mode === "tournament" && <p>Búsqueda de torneo</p>}
            {search.error && <Alert variant="info" title={search.error} />}
            {waiting && (
              <div className="form__actions">
                <Button
                  variant="secondary"
                  busy={busy}
                  onClick={() => void run(() => searches.cancel(search.id))}
                >
                  Salir de la búsqueda
                </Button>
              </div>
            )}
          </div>
        ) : available.length === 0 ? (
          <div className="form search-form">
            <Alert variant="info" title="Aún no tienes decks">
              <p>Crea un deck con 12 cartas de tu colección para buscar partida.</p>
            </Alert>
            <div className="form__actions">
              <Link className="button button--primary" to="/mazos/nuevo">
                Crear deck
              </Link>
            </div>
          </div>
        ) : (
          <form
            className="form search-form"
            onSubmit={(event) => {
              event.preventDefault();
              enter();
            }}
          >
            <SelectField
              id="ranked-deck"
              label="Deck"
              value={deckId}
              placeholder="Selecciona un deck"
              options={available.map((deck) => ({ value: deck.id, label: deck.name }))}
              disabled={busy}
              onChange={(value) => {
                operation.reset();
                setDeckId(value);
              }}
            />
            <div className="form__actions">
              <Button type="submit" busy={busy}>
                {busy ? "Enviando…" : "Buscar partida"}
              </Button>
            </div>
          </form>
        ))}
    </section>
  );
}
