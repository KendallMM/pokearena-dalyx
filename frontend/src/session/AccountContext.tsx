import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type {
  PlayerAccount,
  PlayerSession,
  InitialCollectionDelivery,
} from "../api/types";
import { useSession } from "./SessionContext";

interface AccountValue {
  account: PlayerAccount | null;
  initialCollection: InitialCollectionDelivery | null;
  enter: (session: PlayerSession) => void;
  logOut: () => void;
}

const AccountContext = createContext<AccountValue | null>(null);

/* App del jugador, mensajes 38–39: conserva el resultado del backend en memoria.
 * La cuenta, su rol y el bearer provienen del mismo inicio de sesión verificado.
 */
export function AccountProvider({ children }: { children: ReactNode }) {
  const { clearToken, setToken, hasToken } = useSession();
  const [account, setAccount] = useState<PlayerAccount | null>(null);
  const [initialCollection, setInitialCollection] =
    useState<InitialCollectionDelivery | null>(null);

  const enter = useCallback(
    (session: PlayerSession) => {
      // Se usa access_token de Poké-Arena; la identidad de Google ya fue intercambiada.
      setToken(session.access_token, session.expires_at);
      setAccount(session.player);
      setInitialCollection(session.initial_collection);
    },
    [setToken],
  );

  const logOut = useCallback(() => {
    clearToken();
    setAccount(null);
    setInitialCollection(null);
  }, [clearToken]);

  const value = useMemo(
    () => ({ account: hasToken ? account : null, initialCollection, enter, logOut }),
    [account, hasToken, initialCollection, enter, logOut],
  );
  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount(): AccountValue {
  const value = useContext(AccountContext);
  if (!value) throw new Error("useAccount debe usarse dentro de un AccountProvider.");
  return value;
}
