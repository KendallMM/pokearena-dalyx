import { useEffect, useRef } from "react";

/**
 * App del jugador, mensaje 5: recibe el regreso de Google en la ventana emergente.
 * Retira el token del fragmento y lo entrega al origen propio. El servidor será
 * quien verifique su firma antes de usarlo para identificar al jugador.
 */
export function GoogleCallbackPage() {
  const handled = useRef(false);
  useEffect(() => {
    // Un único envío evita repetir el resultado si React vuelve a ejecutar el efecto.
    if (handled.current) return;
    handled.current = true;
    const result = new URLSearchParams(window.location.hash.slice(1));
    window.history.replaceState(null, "", window.location.pathname);
    if (!window.opener) return;
    window.opener.postMessage(
      {
        type: "pokearena.google.identity",
        state: result.get("state"),
        credential: result.get("id_token"),
        error: result.get("error"),
      },
      window.location.origin,
    );
    // El padre cierra la ventana después de recibir el mensaje.
  }, []);

  return (
    <main className="auth">
      <p>Completando inicio de sesión…</p>
    </main>
  );
}
