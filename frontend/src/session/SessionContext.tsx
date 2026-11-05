import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface SessionValue {
  /** Hay un token cargado (no significa que el servidor lo acepte). */
  hasToken: boolean;
  /** Lee el token en el momento de cada llamada a la API. */
  getToken: () => string | null;
  setToken: (token: string, expiresAt?: string) => void;
  clearToken: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/**
 * Credencial bearer solo en memoria: no se persiste en el almacenamiento web.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const tokenRef = useRef<string | null>(null);
  const expirationRef = useRef<number | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [expiration, setExpiration] = useState<number | null>(null);

  const getToken = useCallback(() => {
    if (expirationRef.current !== null && Date.now() >= expirationRef.current)
      return null;
    return tokenRef.current;
  }, []);
  const setToken = useCallback((token: string, expiresAt?: string) => {
    const clean = token.trim();
    const expiry = expiresAt ? Date.parse(expiresAt) : null;
    if (expiry !== null && (!Number.isFinite(expiry) || expiry <= Date.now())) return;
    tokenRef.current = clean || null;
    expirationRef.current = expiry;
    setExpiration(expiry);
    setHasToken(clean !== "");
  }, []);
  const clearToken = useCallback(() => {
    tokenRef.current = null;
    expirationRef.current = null;
    setExpiration(null);
    setHasToken(false);
  }, []);

  useEffect(() => {
    // Retira los datos del prototipo que almacenaba cuentas y tokens localmente.
    try {
      sessionStorage.removeItem("pokearena.session.token");
      sessionStorage.removeItem("pokearena.session.account");
      localStorage.removeItem("pokearena.accounts");
    } catch {
      // El inicio de sesión funciona también sin almacenamiento web.
    }
  }, []);

  useEffect(() => {
    if (expiration === null) return;
    const timer = window.setTimeout(clearToken, Math.max(0, expiration - Date.now()));
    return () => window.clearTimeout(timer);
  }, [expiration, clearToken]);

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
