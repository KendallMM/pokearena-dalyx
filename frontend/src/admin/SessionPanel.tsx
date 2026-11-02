import { useState, type FormEvent } from "react";

import { useSession } from "../session/SessionContext";
import { Button } from "../ui";

/**
 * Sesión de desarrollo: se pega el token de un administrador. Se reemplaza por el
 * inicio de sesión real cuando exista la historia de Sesiones.
 */
export function SessionPanel() {
  const { hasToken, setToken, clearToken } = useSession();
  const [draft, setDraft] = useState("");

  function save(event: FormEvent) {
    event.preventDefault();
    setToken(draft);
    setDraft("");
  }

  if (hasToken) {
    return (
      <div className="session">
        <span className="session__status">Sesión de desarrollo activa</span>
        <Button variant="secondary" onClick={clearToken}>
          Cerrar sesión
        </Button>
      </div>
    );
  }

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
