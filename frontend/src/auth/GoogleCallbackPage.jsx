import { useEffect, useRef } from "react";

/** Entrega el resultado solo a la ventana de origen y retira el fragmento sensible. */
export function GoogleCallbackPage() {
  const handled = useRef(false);
  useEffect(() => {
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
