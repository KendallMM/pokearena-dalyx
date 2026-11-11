import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/errors";
import { COST_RANGE } from "../../admin/cards/cardRules";
import { Alert, Button, SelectField, Spinner, TextField } from "../../ui";
import { CatalogCardItem } from "./CatalogCardItem";
import {
  catalogFieldFromApi,
  EMPTY_CATALOG_FILTERS,
  toCatalogCriteria,
  validateCatalogFilters,
  type CatalogFilterErrors,
  type CatalogFilterField,
  type CatalogFilterValues,
} from "./catalogRules";
import { useCardTypes, useCatalog } from "./useCatalog";

export const RETRY_MESSAGE = "No se pudo cargar el catálogo. Inténtalo de nuevo.";
export const SESSION_EXPIRED_MESSAGE =
  "Tu sesión venció. Cierra sesión y vuelve a entrar para ver el catálogo.";
export const PLAYERS_ONLY_MESSAGE =
  "El catálogo y la colección son para cuentas de jugador.";

/* Convierte un error de la API en el mensaje o el filtro que debe verse. */
function describeError(error: unknown): {
  field?: CatalogFilterField;
  message: string;
} {
  if (error instanceof ApiError) {
    if (error.isNotAuthenticated) return { message: SESSION_EXPIRED_MESSAGE };
    if (error.isForbidden) return { message: PLAYERS_ONLY_MESSAGE };
    if (error.status === 400) {
      const field = catalogFieldFromApi(error.field);
      return field ? { field, message: error.message } : { message: error.message };
    }
  }
  return { message: RETRY_MESSAGE };
}

/* Pantalla Catálogo: explorar todas las cartas y ver cuáles posee el jugador. */
export function CatalogPage() {
  const { state: typesState, reload } = useCardTypes();
  const { state, search, loadMore } = useCatalog();
  const [values, setValues] = useState<CatalogFilterValues>(EMPTY_CATALOG_FILTERS);
  const [errors, setErrors] = useState<CatalogFilterErrors>({});

  useEffect(() => {
    if (typesState.status === "ready") void search({});
  }, [typesState.status, search]);

  const problem = state.status === "error" ? describeError(state.error) : null;

  // Un error de un filtro va debajo de ese filtro, y se borra al corregirlo.
  const filterField = problem?.field;
  const filterMessage = problem?.message;
  useEffect(() => {
    if (filterField) {
      setErrors((current) => ({ ...current, [filterField]: filterMessage }));
    }
  }, [filterField, filterMessage]);

  function change(field: CatalogFilterField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function apply(next: CatalogFilterValues) {
    const found = validateCatalogFilters(next);
    setErrors(found);
    if (Object.values(found).some(Boolean)) return;
    void search(toCatalogCriteria(next));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    apply(values);
  }

  function toggleOwnedOnly(ownedOnly: boolean) {
    // Ver solo mis cartas se aplica al instante, con los demás filtros activos.
    const next = { ...values, ownedOnly };
    setValues(next);
    apply(next);
  }

  function clear() {
    setValues(EMPTY_CATALOG_FILTERS);
    setErrors({});
    void search({});
  }

  const searching = state.status === "searching";
  const { items, nextCursor } = state;

  if (typesState.status === "loading") {
    return <Spinner label="Cargando el catálogo…" />;
  }
  if (typesState.status === "error") {
    return (
      <section className="page">
        <Alert variant="error" title="No se pudo abrir el catálogo">
          <p>{describeError(typesState.error).message}</p>
        </Alert>
        <Button variant="secondary" onClick={reload}>
          Reintentar
        </Button>
      </section>
    );
  }

  return (
    <section aria-labelledby="catalog-title" className="page">
      <h1 id="catalog-title">Catálogo</h1>
      <p className="page__intro">
        Explora todas las cartas y mira cuáles tienes para planificar tus mazos.
      </p>

      <form className="form search-form" onSubmit={handleSubmit} noValidate>
        <div className="form__row catalog-filters">
          <SelectField
            id="catalog-card-type"
            label="Tipo"
            placeholder="Todos"
            value={values.cardType}
            options={typesState.cardTypes.map((t) => ({
              value: t.code,
              label: t.name,
            }))}
            error={errors.cardType}
            onChange={(value) => change("cardType", value)}
          />
          <TextField
            id="catalog-cost-min"
            label="Costo mínimo"
            hint={`De ${COST_RANGE.min} a ${COST_RANGE.max}`}
            inputMode="numeric"
            value={values.costMin}
            error={errors.costMin}
            onChange={(value) => change("costMin", value)}
          />
          <TextField
            id="catalog-cost-max"
            label="Costo máximo"
            hint={`De ${COST_RANGE.min} a ${COST_RANGE.max}`}
            inputMode="numeric"
            value={values.costMax}
            error={errors.costMax}
            onChange={(value) => change("costMax", value)}
          />
        </div>
        <div className="form__actions">
          <Button type="submit" busy={searching}>
            {searching ? "Buscando…" : "Buscar"}
          </Button>
          <Button type="button" variant="secondary" onClick={clear}>
            Limpiar
          </Button>
          <label className="catalog-owned-toggle">
            <input
              type="checkbox"
              checked={values.ownedOnly}
              onChange={(event) => toggleOwnedOnly(event.target.checked)}
            />
            Ver solo mis cartas
          </label>
        </div>
      </form>

      <div className="search-area" aria-live="polite">
        {searching && <Spinner label="Buscando cartas…" />}

        {problem && !problem.field && (
          <Alert variant="error" title="No se pudo cargar el catálogo">
            <p>{problem.message}</p>
          </Alert>
        )}

        {state.status === "done" && items.length === 0 && (
          <Alert variant="info" title="Sin resultados">
            <p>
              {values.ownedOnly
                ? "No tienes cartas con esos filtros."
                : "No hay cartas con esos filtros."}
            </p>
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
                <CatalogCardItem key={card.code} card={card} />
              ))}
            </ul>
          </>
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
