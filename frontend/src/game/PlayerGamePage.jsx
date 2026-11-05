import { useAccount } from "../session/AccountContext";
import { Alert, Button } from "../ui";
import { MatchPage } from "./MatchPage";

/** Conserva la partida existente y comunica el resultado de la entrega inicial. */
export function PlayerGamePage() {
  const { account, initialCollection, logOut } = useAccount();
  return (
    <>
      <header className="site-bar">
        <p>Hola, {account?.name}</p>
        <Button variant="secondary" onClick={logOut}>
          Cerrar sesión
        </Button>
      </header>
      {initialCollection && (
        <Alert variant="info" title="Colección inicial">
          <p>{initialCollection.message}</p>
        </Alert>
      )}
      <MatchPage />
    </>
  );
}
