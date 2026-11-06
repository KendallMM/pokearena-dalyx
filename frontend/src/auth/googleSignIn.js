/**
 * App del jugador → Google (sistema externo): mensajes 2–5 del diagrama.
 * Google autentica al usuario; esta función recibe su resultado para que el
 * backend compruebe después la identidad. Aquí aún no existe sesión interna.
 */

export class GoogleLoginCancelled extends Error {
  constructor() {
    super("Se canceló el inicio de sesión. No se inició ninguna sesión.");
    this.name = "GoogleLoginCancelled";
  }
}

/**
 * @param {import('../api/types').GoogleChallenge} challenge
 * @param {Window} popup
 * @returns {Promise<string>}
 */
export function requestGoogleIdentity(challenge, popup) {
  // state comprueba el regreso al intento correcto; nonce viajará firmado en
  // el token y el backend lo cotejará con su desafío de un solo uso.
  const state = crypto.randomUUID();
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.search = new URLSearchParams({
    client_id: challenge.client_id,
    redirect_uri: `${window.location.origin}/auth/google/callback`,
    response_type: "id_token",
    scope: "openid email profile",
    nonce: challenge.nonce,
    state,
    prompt: "select_account",
  }).toString();

  return new Promise((resolve, reject) => {
    function finish(error, credential) {
      window.removeEventListener("message", receive);
      window.clearInterval(closedTimer);
      window.clearTimeout(timeout);
      popup.close();
      if (error) reject(error);
      else resolve(credential);
    }

    function receive(event) {
      // Solo se acepta el callback propio de la ventana abierta para este intento.
      // Recibir una cadena no prueba su firma: esa comprobación es del backend.
      if (
        event.origin !== window.location.origin ||
        event.source !== popup ||
        event.data?.type !== "pokearena.google.identity" ||
        event.data.state !== state
      )
        return;
      // Rama de cancelación/rechazo del mensaje 3: termina sin intercambiar token.
      if (event.data.error === "access_denied") finish(new GoogleLoginCancelled());
      else if (event.data.error || typeof event.data.credential !== "string") {
        finish(
          new Error(
            "Google no pudo completar el inicio de sesión. Inténtalo de nuevo.",
          ),
        );
      } else finish(null, event.data.credential);
    }

    window.addEventListener("message", receive);
    // Cerrar la ventana también equivale a cancelar, aunque Google no responda.
    const closedTimer = window.setInterval(() => {
      if (popup.closed) finish(new GoogleLoginCancelled());
    }, 300);
    const timeout = window.setTimeout(() => {
      finish(new Error("El intento de inicio de sesión venció. Inténtalo de nuevo."));
    }, challenge.expires_in * 1000);
    popup.location.href = url.toString();
  });
}
