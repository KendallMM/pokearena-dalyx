import { Link } from "react-router-dom";

import { useAccount } from "../session/AccountContext";
import { useSession } from "../session/SessionContext";
import { Alert } from "../ui";
import { MENU_OPTIONS } from "./menuOptions";

/* Primera pantalla después de entrar: desde aquí se elige qué hacer. */
export function MainMenuPage() {
  const { account } = useAccount();
  const { hasToken } = useSession();

  return (
    <section aria-labelledby="main-menu-title" className="page">
      <h1 id="main-menu-title">Menú principal</h1>
      <p className="page__intro">Hola, {account?.name}. ¿Qué quieres hacer?</p>

      {!hasToken && (
        <Alert variant="info" title="Falta el token">
          <p>Para crear cartas y ubicaciones, pega un token en la barra superior.</p>
        </Alert>
      )}

      <ul className="main-menu">
        {MENU_OPTIONS.map((option) => (
          <li key={option.to}>
            <Link className="main-menu__option" to={option.to}>
              <span className="main-menu__label">{option.label}</span>
              <span className="main-menu__description">{option.description}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
