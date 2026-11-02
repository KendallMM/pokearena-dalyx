import { NavLink, Outlet } from "react-router-dom";

import { SessionPanel } from "./SessionPanel";

/**
 * Estructura común de la App Web del Administrador. Para agregar una pantalla:
 * crea su carpeta en admin/, agrega su ruta en App.tsx y su enlace en `links`.
 */
const links = [{ to: "/admin/cartas/nueva", label: "Crear carta" }];

export function AdminLayout() {
  return (
    <div className="layout">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <header className="layout__header">
        <p className="brand">PokéArena · Administración</p>
        <nav aria-label="Principal">
          <ul className="nav">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to}>{link.label}</NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <SessionPanel />
      </header>
      <main id="main" className="layout__main">
        <Outlet />
      </main>
    </div>
  );
}
