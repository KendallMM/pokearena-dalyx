import { Navigate, NavLink, Outlet } from "react-router-dom";

import { useAccount } from "../session/AccountContext";
import { Button, ThemeToggle } from "../ui";

/* Estructura común de la App del jugador: saludo, navegación y cierre de sesión. */
export function PlayerLayout() {
  const { account, logOut } = useAccount();
  const isPlayer = account?.role === "player";

  if (account?.role === "content_admin") {
    return <Navigate to="/menu" replace />;
  }

  return (
    <div className="layout">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <header className="site-bar player-bar">
        <p>Hola, {account?.name}</p>
        <nav aria-label="Jugador">
          <ul className="player-nav">
            <li>
              <NavLink to="/partida">Área de juego</NavLink>
            </li>
            {isPlayer && (
              <>
                <li>
                  <NavLink to="/catalogo">Catálogo</NavLink>
                </li>
                <li>
                  <NavLink to="/mazos">Mis decks</NavLink>
                </li>
              </>
            )}
          </ul>
        </nav>
        <Button variant="secondary" onClick={logOut}>
          Cerrar sesión
        </Button>
      </header>
      <main id="main" className="layout__main">
        <Outlet />
      </main>
      <ThemeToggle />
    </div>
  );
}
