import { useAccount } from "../session/AccountContext";
import { RankedSearch } from "./RankedSearch";

/**
 * App del jugador, mensaje 39: permite entrar y comunica el resultado de Colección.
 * Un estado pendiente/no disponible se muestra sin invalidar la autenticación.
 */
export function PlayerGamePage() {
  const { initialCollection } = useAccount();
  return <RankedSearch collectionMessage={initialCollection?.message} />;
}
