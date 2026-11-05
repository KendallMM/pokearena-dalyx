import { ApiError } from "../api/errors";

export const NOT_AUTHENTICATED_MESSAGE =
  "No hay una sesión válida. Pega un token vigente en el panel de sesión e inténtalo de nuevo.";
export const FORBIDDEN_MESSAGE =
  "Tu usuario no tiene permiso para esta operación. Se necesita el rol de administrador de contenido.";

/** Mensaje para el administrador cuando falla el acceso. Distingue 401 de 403. */
export function accessDeniedMessage(error: unknown): string | null {
  if (error instanceof ApiError) {
    if (error.isNotAuthenticated) return NOT_AUTHENTICATED_MESSAGE;
    if (error.isForbidden) return FORBIDDEN_MESSAGE;
  }
  return null;
}
