import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import logo from "../../images/pokeball.png";
import { ThemeToggle } from "../ui";
import { SessionPanel } from "./SessionPanel";

/*
 * Estructura común de la App Web del Administrador. Para agregar una pantalla:
 * crea su carpeta en admin/, agrega su ruta en App.tsx y su enlace en `links`.
 */
const links = [
  { to: "/admin/cartas/nueva", label: "Crear carta" },
  { to: "/admin/ubicaciones/nueva", label: "Crear ubicación" },
];

function Brand() {
  return (
    <p className="brand">
      <img className="brand__mark" src={logo} alt="" />
      <span>
        <span className="brand__name">PokéArena</span>
        <span className="brand__area">Administración</span>
      </span>
    </p>
  );
}

export function AdminLayout() {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="layout">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <header className="site-bar">
        <button
          type="button"
          className="menu-button"
          aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={menuOpen}
          aria-controls="menu-panel"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span aria-hidden="true">{menuOpen ? "✕" : "☰"}</span>
        </button>
        <Brand />
        <SessionPanel />
        {menuOpen && (
          <div className="menu-backdrop" onClick={() => setMenuOpen(false)} />
        )}
        <div
          id="menu-panel"
          className={`menu-panel${menuOpen ? " menu-panel--open" : ""}`}
        >
          <h2 className="menu-panel__title">Opciones</h2>
          <nav aria-label="Principal">
            <ul className="nav">
              {links.map((link) => (
                <li key={link.to}>
                  <NavLink to={link.to} onClick={() => setMenuOpen(false)}>
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="layout__main">
        <Outlet />
      </main>
      <ThemeToggle />
    </div>
  );
}
