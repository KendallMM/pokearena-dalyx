/* Lo que se puede hacer desde el menú principal y desde el menú ☰. */
export const MENU_OPTIONS = [
  {
    to: "/admin/cartas/nueva",
    label: "Crear carta",
    description: "Agrega una carta nueva al catálogo.",
  },
  {
    to: "/admin/cartas",
    label: "Buscar cartas",
    description: "Revisa las cartas del catálogo con filtros.",
  },
  {
    to: "/admin/ubicaciones/nueva",
    label: "Crear ubicación",
    description: "Agrega una ubicación para las partidas.",
  },
] as const;
