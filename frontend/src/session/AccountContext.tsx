import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  readCurrentAccount,
  registerAccount,
  saveCurrentAccount,
  verifyAccount,
  type Account,
} from "./localAccounts";
import { useSession } from "./SessionContext";

interface AccountValue {
  account: Account | null;
  register: (input: { name: string; email: string; password: string }) => Promise<void>;
  logIn: (email: string, password: string) => Promise<void>;
  logOut: () => void;
}

const AccountContext = createContext<AccountValue | null>(null);

/* Quién entró a la aplicación. Es aparte del token, que da el acceso a la API. */
export function AccountProvider({ children }: { children: ReactNode }) {
  const { clearToken } = useSession();
  const [account, setAccount] = useState<Account | null>(readCurrentAccount);

  const enter = useCallback((next: Account) => {
    saveCurrentAccount(next);
    setAccount(next);
  }, []);

  const register = useCallback<AccountValue["register"]>(
    async (input) => enter(await registerAccount(input)),
    [enter],
  );
  const logIn = useCallback<AccountValue["logIn"]>(
    async (email, password) => enter(await verifyAccount(email, password)),
    [enter],
  );
  // También se quita el token: quien entre después no debe heredar ese acceso.
  const logOut = useCallback(() => {
    saveCurrentAccount(null);
    clearToken();
    setAccount(null);
  }, [clearToken]);

  const value = useMemo(
    () => ({ account, register, logIn, logOut }),
    [account, register, logIn, logOut],
  );
  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount(): AccountValue {
  const value = useContext(AccountContext);
  if (!value) throw new Error("useAccount debe usarse dentro de un AccountProvider.");
  return value;
}
