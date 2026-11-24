import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useOperationKey } from "../admin/cards/operationId";
import { useApi } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { MatchSearch } from "../api/searches";
import type { PlayerDeck } from "../api/types";
import { Alert, Button, SelectField, Spinner } from "../ui";

const pollSeconds = Number(import.meta.env.VITE_SEARCH_POLL_SECONDS);
const POLL_MS =
  pollSeconds > 0 && Number.isFinite(pollSeconds) ? pollSeconds * 1000 : 3000;

export function RankedSearch({ collectionMessage }: { collectionMessage?: string }) {
  const { decks, searches } = useApi();
  const [available, setAvailable] = useState<PlayerDeck[]>([]);
  const [search, setSearch] = useState<MatchSearch | null>(null);
  const [deckId, setDeckId] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const [matchNotice, setMatchNotice] = useState<{
    title: string;
    message: string;
  }>();
  const operation = useOperationKey();
  const botOperation = useOperationKey();
  const navigate = useNavigate();
  const submitting = useRef(false);
  const waiting = search?.status === "waiting" || search?.status === "reserved";
  const found = search?.status === "found";

  useEffect(() => {
    let active = true;
    const current = searches.current().catch((failure: unknown) => {
      if (failure instanceof ApiError && failure.status === 404) return null;
      throw failure;
    });
    Promise.all([decks.list(), current]).then(
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
    let active = true;
    let timer: number;
    async function poll() {
      try {
        const next = await searches.current();
        // Una consulta anterior no debe reemplazar el resultado de una acción.
        if (!active || submitting.current) return;
        setSearch(next);
        setError(null);
        if (next.status === "waiting" || next.status === "reserved") {
          timer = window.setTimeout(poll, POLL_MS);
        }
      } catch (failure) {
        if (!active || submitting.current) return;
        setError(failure as Error);
        if (
          !(failure instanceof ApiError) ||
          ![401, 403, 404].includes(failure.status)
        ) {
          timer = window.setTimeout(poll, POLL_MS);
        }
      }
    }
    timer = window.setTimeout(poll, POLL_MS);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [waitingId, busy, searches]);

  const matchId = search?.match_id;
  useEffect(() => {
    if (found && matchId)
      navigate(`/partida/${encodeURIComponent(matchId)}`, {
        replace: true,
        state: { matchNotice },
      });
  }, [found, matchId, navigate, matchNotice]);

  async function run(action: () => Promise<MatchSearch>, kind?: "cancel" | "bot") {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    setMatchNotice(undefined);
    try {
      const next = await action();
      setSearch(next);
      operation.reset();
      botOperation.reset();
    } catch (failure) {
      setError(failure as Error);
      if (failure instanceof ApiError && failure.status === 409) {
        // Conserva el motivo si la consulta posterior lleva a la partida.
        if (kind === "bot" || (kind === "cancel" && failure.field === "match_id")) {
          setMatchNotice({
            title:
              kind === "bot"
                ? "No se pudo aceptar la oferta del bot"
                : "No se pudo cancelar la búsqueda",
            message: failure.message,
          });
        }
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
      {ready && !search && (
        <Alert variant="info" title="No tienes una búsqueda de partida" />
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
      {(search?.status === "cancelled" || search?.status === "expired") && (
        <Alert
          variant="info"
          title={
            search.already_ended
              ? "La búsqueda ya había terminado"
              : search.status === "expired"
                ? "Búsqueda expirada por inactividad"
                : "Búsqueda cancelada"
          }
        >
          {search.already_ended && (
            <p>
              {search.status === "expired" ? "Expirada por inactividad." : "Cancelada."}
            </p>
          )}
        </Alert>
      )}
      {!ready && !error && <Spinner label="Cargando tus decks y tu búsqueda…" />}
      {ready &&
        (waiting || found ? (
          <div className="form search-form ranked-queue">
            {waiting ? (
              <Spinner label="Buscando rival" />
            ) : (
              <Alert
                variant="success"
                title={`Partida encontrada: ${search.match_id}`}
              />
            )}
            {/* El tiempo mostrado proviene de la última consulta al servidor. */}
            <dl className="ranked-queue__details">
              {waiting && (
                <div className="ranked-queue__time">
                  <dt>Tiempo en la fila</dt>
                  <dd>
                    {search.wait_seconds === undefined
                      ? "—"
                      : `${Math.floor(search.wait_seconds / 60)}:${String(
                          search.wait_seconds % 60,
                        ).padStart(2, "0")}`}
                  </dd>
                </div>
              )}
              <div>
                <dt>Deck seleccionado</dt>
                <dd>
                  {available.find((deck) => deck.id === search.deck_id)?.name ??
                    search.deck_id}
                </dd>
              </div>
              {search.mode === "tournament" && (
                <div>
                  <dt>Tipo de búsqueda</dt>
                  <dd>Torneo</dd>
                </div>
              )}
            </dl>
            {search.error && <Alert variant="info" title={search.error} />}
            {waiting && (
              <div className="form__actions ranked-queue__actions">
                {search.bot_available && (
                  <Button
                    busy={busy}
                    onClick={() =>
                      void run(async () => {
                        const result = await searches.acceptBot(
                          search.id,
                          botOperation.current(),
                        );
                        return {
                          ...search,
                          status: "found",
                          match_id: result.match_id,
                        };
                      }, "bot")
                    }
                  >
                    Jugar contra el bot
                  </Button>
                )}
                <Button
                  variant="secondary"
                  busy={busy}
                  onClick={() => void run(() => searches.cancel(search.id), "cancel")}
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
