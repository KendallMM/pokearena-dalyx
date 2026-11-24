import { ApiError } from "../../api/errors";

export const DECK_SIZE = 12;
export const DECK_NAME_MAX_LENGTH = 40;

export const SESSION_EXPIRED_MESSAGE =
  "Tu sesión venció. Cierra sesión y vuelve a entrar para ver tus decks.";
export const PLAYERS_ONLY_MESSAGE = "Los decks son para cuentas de jugador.";
export const RETRY_MESSAGE = "No se pudo completar la operación. Inténtalo de nuevo.";

/* Respuesta rápida antes de enviar; las reglas de verdad las aplica el servidor. */
export function validateDeck(
  name: string,
  selected: number,
): { name?: string; cards?: string } {
  const errors: { name?: string; cards?: string } = {};
  const cleaned = name.trim();
  if (!cleaned || cleaned.length > DECK_NAME_MAX_LENGTH) {
    errors.name = `El nombre debe tener entre 1 y ${DECK_NAME_MAX_LENGTH} caracteres.`;
  }
  if (selected !== DECK_SIZE) {
    errors.cards = `Un deck debe tener exactamente ${DECK_SIZE} cartas; llevas ${selected}.`;
  }
  return errors;
}

/* Mensaje para un error de la API. */
export function deckErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.isNotAuthenticated) return SESSION_EXPIRED_MESSAGE;
    if (error.isForbidden) return PLAYERS_ONLY_MESSAGE;
    if ([400, 404, 409].includes(error.status)) return error.message;
  }
  return RETRY_MESSAGE;
}
