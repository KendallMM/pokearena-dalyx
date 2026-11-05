/* Lo que se puede hacer desde el menú principal y desde el menú ☰. */
export const MENU_OPTIONS = [
  {
    to: "/admin/cartas/nueva",
    label: "Crear carta",
    description: "Agrega una carta nueva al catálogo.",
  },
  {
    to: "/admin/ubicaciones/nueva",
    label: "Crear ubicación",
    description: "Agrega una ubicación para las partidas.",
  },
  {
    to: "/partida",
    label: "Área de juego",
    description: "Mira el diseño de la partida, con datos de ejemplo.",
  },
] as const;
