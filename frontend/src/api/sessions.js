/** Servicios de sesión sobre el cliente HTTP compartido. */

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
      return http.postJson("/v1/sesiones/google", { credential });
    },
    /** @returns {Promise<import('./types').PlayerAccount>} */
    me() {
      return http.getJson("/v1/jugadores/yo");
    },
  };
}
