import { useAccount } from "../session/AccountContext";
import { Alert } from "../ui";
import { MatchPage } from "./MatchPage";

/**
 * App del jugador, mensaje 39: permite entrar y comunica el resultado de Colección.
 * Un estado pendiente/no disponible se muestra sin invalidar la autenticación.
 */
export function PlayerGamePage() {
  const { initialCollection } = useAccount();
  return (
    <>
      {initialCollection && (
        <Alert variant="info" title="Colección inicial">
          <p>{initialCollection.message}</p>
        </Alert>
      )}
      <MatchPage />
    </>
  );
}
