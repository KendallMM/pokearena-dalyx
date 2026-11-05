import { useState, type FormEvent } from "react";

import { useSession } from "../session/SessionContext";
import { Button } from "../ui";

/*
 * Token de desarrollo: se pega el de un administrador y es lo que da acceso a la API.
 * Se reemplaza por el inicio de sesión real cuando exista la historia de Sesiones.
 */
export function SessionPanel() {
  const { hasToken, setToken } = useSession();
  const [draft, setDraft] = useState("");

  function save(event: FormEvent) {
    event.preventDefault();
    setToken(draft);
    setDraft("");
  }

  // Con un token cargado no hay nada que mostrar: se quita al cerrar sesión.
  if (hasToken) return null;

  return (
    <form className="session" onSubmit={save}>
      <label htmlFor="session-token" className="session__label">
        Token de sesión (solo desarrollo)
      </label>
      <input
        id="session-token"
        className="input"
        type="password"
        autoComplete="off"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      <Button type="submit" variant="secondary" disabled={!draft.trim()}>
        Usar token
      </Button>
    </form>
  );
}
