import { createContext, useContext, useMemo, type ReactNode } from "react";

import { useSession } from "../session/SessionContext";
import { createCardsApi, type CardsApi } from "./cards";
import { createHttpClient } from "./httpClient";
import { createReferencesApi, type ReferencesApi } from "./references";

/** Servicios de la API que usan las pantallas. Cada pantalla pide solo los suyos. */
export interface ApiServices {
  references: ReferencesApi;
  cards: CardsApi;
}

const ApiContext = createContext<ApiServices | null>(null);

/** Arma los servicios reales sobre el cliente HTTP y la sesión actual. */
export function ApiProvider({ children }: { children: ReactNode }) {
  const { getToken } = useSession();
  const services = useMemo<ApiServices>(() => {
    const http = createHttpClient({ getToken });
    return { references: createReferencesApi(http), cards: createCardsApi(http) };
  }, [getToken]);
  return <ApiContext.Provider value={services}>{children}</ApiContext.Provider>;
}

/** Para pruebas y para cambiar la implementación sin tocar las pantallas. */
export function ApiServicesProvider({
  services,
  children,
}: {
  services: ApiServices;
  children: ReactNode;
}) {
  return <ApiContext.Provider value={services}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiServices {
  const services = useContext(ApiContext);
  if (!services) throw new Error("useApi debe usarse dentro de un ApiProvider.");
  return services;
}
