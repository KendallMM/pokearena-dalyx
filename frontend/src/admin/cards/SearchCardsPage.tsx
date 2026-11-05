import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/errors";
import { Alert, Button, SelectField, Spinner, TextField } from "../../ui";
import { accessDeniedMessage } from "../accessMessages";
import { BackToMenu } from "../BackToMenu";
import { ReferencesStatus } from "../ReferencesStatus";
import { CardSearchResultItem } from "./CardSearchResultItem";
import { COST_RANGE, NAME_MAX_LENGTH, POWER_RANGE } from "./cardRules";
import {
  EMPTY_CARD_SEARCH,
  searchFieldFromApi,
  toCardSearchCriteria,
  validateCardSearch,
  type CardSearchErrors,
  type CardSearchField,
  type CardSearchValues,
} from "./cardSearchRules";
import { useCardSearch } from "./useCardSearch";
import { useReferences } from "./useReferences";

const RETRY_MESSAGE = "No se pudo completar la búsqueda. Inténtalo de nuevo.";

/* Convierte un error de la consulta en el mensaje o el filtro que debe verse. */
function describeSearchError(error: unknown): {
  field?: CardSearchField;
  message: string;
} {
  const denied = accessDeniedMessage(error);
  if (denied) return { message: denied };
  if (error instanceof ApiError && error.status === 400) {
    const field = searchFieldFromApi(error.field);
    return field ? { field, message: error.message } : { message: error.message };
  }
  return { message: RETRY_MESSAGE };
}

/* Pantalla Buscar cartas: filtros, resultados y páginas siguientes. */
export function SearchCardsPage() {
  const { state: referencesState, reload } = useReferences();
  const { state: searchState, search, loadMore } = useCardSearch();
  const [values, setValues] = useState<CardSearchValues>(EMPTY_CARD_SEARCH);
  const [errors, setErrors] = useState<CardSearchErrors>({});

  // Al abrir, y al cambiar de sesión (los catálogos se recargan), repite la consulta.
  useEffect(() => {
    if (referencesState.status === "ready") void search();
  }, [referencesState.status, search]);

  const problem =
    searchState.status === "error" ? describeSearchError(searchState.error) : null;

  // Un error de un filtro va debajo de ese filtro, y se borra al corregirlo.
  const filterField = problem?.field;
  const filterMessage = problem?.message;
  useEffect(() => {
    if (filterField) {
      setErrors((current) => ({ ...current, [filterField]: filterMessage }));
    }
  }, [filterField, filterMessage]);

  function change(field: CardSearchField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateCardSearch(values);
    setErrors(found);
    if (Object.values(found).some(Boolean)) return;
    void search(toCardSearchCriteria(values));
  }

  function clear() {
    setValues(EMPTY_CARD_SEARCH);
    setErrors({});
    void search({});
  }

  const searching = searchState.status === "searching";
  const { items, nextCursor } = searchState;

  function field(name: CardSearchField, label: string, hint?: string) {
    return (
      <TextField
        id={`search-${name}`}
        label={label}
        hint={hint}
        inputMode={
          name.startsWith("cost") || name.startsWith("power") ? "numeric" : "text"
        }
        maxLength={name === "name" ? NAME_MAX_LENGTH : undefined}
        value={values[name]}
        error={errors[name]}
        onChange={(value) => change(name, value)}
      />
    );
  }

  return (
    <section aria-labelledby="search-cards-title" className="page">
      <h1 id="search-cards-title">Buscar cartas</h1>
      <p className="page__intro">
        Usa los filtros que quieras, o ninguno para ver todo el catálogo.
      </p>

      <ReferencesStatus
        state={referencesState}
        reload={reload}
        errorMessage="No pudimos cargar los tipos, rarezas y habilidades. Inténtalo de nuevo."
      />

      {referencesState.status === "ready" && (
        <>
          <form className="form search-form" onSubmit={handleSubmit} noValidate>
            <div className="form__row">
              {field("code", "Código", "Exacto, por ejemplo PKA-FUE-001.")}
              {field("name", "Nombre", "Parte del nombre; ignora mayúsculas y tildes.")}
            </div>
            <div className="form__row">
              <SelectField
                id="search-card-type"
                label="Tipo"
                placeholder="Todos"
                value={values.cardType}
                options={referencesState.references.card_types.map((t) => ({
                  value: t.code,
                  label: t.name,
                }))}
                error={errors.cardType}
                onChange={(value) => change("cardType", value)}
              />
              <SelectField
                id="search-rarity"
                label="Rareza"
                placeholder="Todas"
                value={values.rarity}
                options={referencesState.references.rarities.map((r) => ({
                  value: r.code,
                  label: r.name,
                }))}
                error={errors.rarity}
                onChange={(value) => change("rarity", value)}
              />
              <SelectField
                id="search-ability"
                label="Habilidad"
                placeholder="Todas"
                value={values.ability}
                options={referencesState.references.abilities.map((a) => ({
                  value: a.code,
                  label: a.name,
                }))}
                error={errors.ability}
                onChange={(value) => change("ability", value)}
              />
            </div>
            <div className="form__row">
              {field(
                "costMin",
                "Costo mínimo",
                `De ${COST_RANGE.min} a ${COST_RANGE.max}`,
              )}
              {field(
                "costMax",
                "Costo máximo",
                `De ${COST_RANGE.min} a ${COST_RANGE.max}`,
              )}
              {field(
                "powerMin",
                "Poder mínimo",
                `De ${POWER_RANGE.min} a ${POWER_RANGE.max}`,
              )}
              {field(
                "powerMax",
                "Poder máximo",
                `De ${POWER_RANGE.min} a ${POWER_RANGE.max}`,
              )}
            </div>
            <div className="form__actions">
              <Button type="submit" busy={searching}>
                {searching ? "Buscando…" : "Buscar"}
              </Button>
              <Button type="button" variant="secondary" onClick={clear}>
                Limpiar
              </Button>
              <BackToMenu />
            </div>
          </form>

          <div className="search-area" aria-live="polite">
            {searching && <Spinner label="Buscando cartas…" />}

            {problem && !problem.field && (
              <Alert variant="error" title="No se pudo buscar">
                <p>{problem.message}</p>
              </Alert>
            )}

            {searchState.status === "done" && items.length === 0 && (
              <Alert variant="info" title="Sin resultados">
                <p>No hay cartas con esos filtros.</p>
              </Alert>
            )}

            {items.length > 0 && (
              <>
                <p className="search-area__count">
                  {items.length === 1
                    ? "1 carta mostrada"
                    : `${items.length} cartas mostradas`}
                  {nextCursor !== null && "; hay más"}
                </p>
                <ul className="search-results">
                  {items.map((card) => (
                    <CardSearchResultItem key={card.code} card={card} />
                  ))}
                </ul>
              </>
            )}

            {nextCursor !== null && (
              <div className="search-area__more">
                <Button
                  variant="secondary"
                  busy={searchState.status === "loadingMore"}
                  onClick={() => void loadMore(nextCursor)}
                >
                  {searchState.status === "loadingMore" ? "Cargando…" : "Cargar más"}
                </Button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
