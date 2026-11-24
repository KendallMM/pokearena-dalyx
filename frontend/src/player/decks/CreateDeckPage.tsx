import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useOperationKey } from "../../admin/cards/operationId";
import { useApi } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import { Alert, Button, Spinner, TextField } from "../../ui";
import { useCatalog } from "../catalog/useCatalog";
import { DeckCardItem } from "./DeckCardItem";
import {
  DECK_NAME_MAX_LENGTH,
  DECK_SIZE,
  deckErrorMessage,
  validateDeck,
} from "./deckRules";

/* Pantalla Crear deck: nombre y 12 cartas de la colección del jugador. */
export function CreateDeckPage() {
  const { decks } = useApi();
  const navigate = useNavigate();
  const { state, search, loadMore } = useCatalog();
  const operation = useOperationKey();
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [nameError, setNameError] = useState<string>();
  const [generalError, setGeneralError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void search({ ownedOnly: true });
  }, [search]);

  function changeName(value: string) {
    setName(value);
    setNameError(undefined);
    // Un deck distinto es otra operación: recibe una llave nueva.
    operation.reset();
  }

  function toggle(code: string) {
    setGeneralError(undefined);
    operation.reset();
    setSelected((current) =>
      current.includes(code)
        ? current.filter((value) => value !== code)
        : [...current, code],
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateDeck(name, selected.length);
    setNameError(found.name);
    setGeneralError(found.cards);
    if (found.name || found.cards) return;
    setSubmitting(true);
    try {
      const created = await decks.create(name.trim(), selected, operation.current());
      operation.reset();
      navigate(`/mazos/${created.id}`);
    } catch (error) {
      const message = deckErrorMessage(error);
      if (error instanceof ApiError && error.field === "name") setNameError(message);
      else setGeneralError(message);
      setSubmitting(false);
    }
  }

  const { items, nextCursor } = state;
  const full = selected.length === DECK_SIZE;

  return (
    <section aria-labelledby="new-deck-title" className="page">
      <h1 id="new-deck-title">Crear deck</h1>
      <p className="page__intro">
        Ponle un nombre y elige {DECK_SIZE} cartas distintas de tu colección.
      </p>

      <form className="form search-form" onSubmit={handleSubmit} noValidate>
        <TextField
          id="deck-name"
          label="Nombre del deck"
          hint={`Hasta ${DECK_NAME_MAX_LENGTH} caracteres.`}
          maxLength={DECK_NAME_MAX_LENGTH}
          value={name}
          error={nameError}
          onChange={changeName}
        />
        <p className="deck-counter" aria-live="polite">
          {selected.length} de {DECK_SIZE} cartas elegidas
        </p>
        {generalError && (
          <Alert variant="error" title="No se pudo crear el deck">
            <p>{generalError}</p>
          </Alert>
        )}
        <div className="form__actions">
          <Button type="submit" busy={submitting}>
            {submitting ? "Guardando…" : "Guardar deck"}
          </Button>
          <Link className="button button--secondary" to="/mazos">
            Cancelar
          </Link>
        </div>
      </form>

      <div className="search-area">
        {state.status === "searching" && <Spinner label="Cargando tu colección…" />}
        {state.status === "error" && (
          <Alert variant="error" title="No se pudo cargar tu colección">
            <p>{deckErrorMessage(state.error)}</p>
          </Alert>
        )}
        {state.status === "done" && items.length === 0 && (
          <Alert variant="info" title="Tu colección está vacía">
            <p>Necesitas cartas en tu colección para crear un deck.</p>
          </Alert>
        )}
        {items.length > 0 && (
          <ul className="search-results">
            {items.map((card) => {
              const isSelected = selected.includes(card.code);
              return (
                <DeckCardItem
                  key={card.code}
                  card={card}
                  selection={{
                    selected: isSelected,
                    disabled: full && !isSelected,
                    onToggle: () => toggle(card.code),
                  }}
                />
              );
            })}
          </ul>
        )}
        {nextCursor !== null && (
          <div className="search-area__more">
            <Button
              variant="secondary"
              busy={state.status === "loadingMore"}
              onClick={() => void loadMore(nextCursor)}
            >
              {state.status === "loadingMore" ? "Cargando…" : "Cargar más"}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
