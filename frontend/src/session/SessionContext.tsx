import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { readToken, removeToken, saveToken } from "./tokenStorage";

interface SessionValue {
  /** Hay un token cargado (no significa que el servidor lo acepte). */
  hasToken: boolean;
  /** Lee el token en el momento de cada llamada a la API. */
  getToken: () => string | null;
  setToken: (token: string) => void;
  clearToken: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/**
 * Sesión de la interfaz. Por ahora el token se pega a mano (sesión de desarrollo);
 * el inicio de sesión real llegará con la historia de Sesiones.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const tokenRef = useRef<string | null>(readToken());
  const [hasToken, setHasToken] = useState(tokenRef.current !== null);

  const getToken = useCallback(() => tokenRef.current, []);
  const setToken = useCallback((token: string) => {
    const clean = token.trim();
    tokenRef.current = clean || null;
    if (clean) saveToken(clean);
    else removeToken();
    setHasToken(clean !== "");
  }, []);
  const clearToken = useCallback(() => {
    tokenRef.current = null;
    removeToken();
    setHasToken(false);
  }, []);

  const value = useMemo(
    () => ({ hasToken, getToken, setToken, clearToken }),
    [hasToken, getToken, setToken, clearToken],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession debe usarse dentro de un SessionProvider.");
  return value;
}
