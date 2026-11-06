/**
 * App del jugador → API Gateway, mensaje 6: intercambio público de identidad.
 * El prefijo /api lo agrega el cliente HTTP y Vite lo retira al llegar al backend.
 */

/** @param {import('./httpClient').HttpClient} http */
export function createSessionsApi(http) {
  return {
    /** @returns {Promise<import('./types').GoogleChallenge>} */
    challenge() {
      return http.getJson("/v1/sesiones/google/desafio");
    },
    /**
     * @param {string} credential
     * @returns {Promise<import('./types').PlayerSession>}
     */
    signInGoogle(credential) {
      // El token de Google viaja en el cuerpo para autenticar. La respuesta
      // contendrá el JWT de Poké-Arena usado en las siguientes solicitudes.
      return http.postJson("/v1/sesiones/google", { credential });
    },
    /** @returns {Promise<import('./types').PlayerAccount>} */
    me() {
      return http.getJson("/v1/jugadores/yo");
    },
  };
}
