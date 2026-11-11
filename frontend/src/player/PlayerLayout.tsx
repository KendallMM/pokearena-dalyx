import { NavLink, Outlet, useMatch } from "react-router-dom";

import { useAccount } from "../session/AccountContext";
import { Button, ThemeToggle } from "../ui";

/* Estructura común de la App del jugador: saludo, navegación y cierre de sesión. */
export function PlayerLayout() {
  const { account, logOut } = useAccount();
  const isPlayer = account?.role === "player";
  // El tablero de la partida trae su propio <main> y usa todo el ancho; las demás
  // pantallas van en el mismo contenedor centrado que la App del Administrador.
  const isMatch = useMatch("/partida") !== null;

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
              <li>
                <NavLink to="/catalogo">Catálogo</NavLink>
              </li>
            )}
            {account?.role === "content_admin" && (
              <li>
                <NavLink to="/menu">Administración</NavLink>
              </li>
            )}
          </ul>
        </nav>
        <Button variant="secondary" onClick={logOut}>
          Cerrar sesión
        </Button>
      </header>
      {isMatch ? (
        <Outlet />
      ) : (
        <main id="main" className="layout__main">
          <Outlet />
        </main>
      )}
      <ThemeToggle />
    </div>
  );
}
