/** OIDC del navegador: solicita solo identidad, sin permisos para APIs de Google. */

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
      if (
        event.origin !== window.location.origin ||
        event.source !== popup ||
        event.data?.type !== "pokearena.google.identity" ||
        event.data.state !== state
      )
        return;
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
    const closedTimer = window.setInterval(() => {
      if (popup.closed) finish(new GoogleLoginCancelled());
    }, 300);
    const timeout = window.setTimeout(() => {
      finish(new Error("El intento de inicio de sesión venció. Inténtalo de nuevo."));
    }, challenge.expires_in * 1000);
    popup.location.href = url.toString();
  });
}
