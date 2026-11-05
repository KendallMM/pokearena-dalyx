import { Navigate, Outlet } from "react-router-dom";

import { useAccount } from "../session/AccountContext";

/* Las pantallas dentro de esta ruta piden haber entrado antes. */
export function RequireAccount() {
  const { account } = useAccount();
  return account ? <Outlet /> : <Navigate to="/login" replace />;
}
