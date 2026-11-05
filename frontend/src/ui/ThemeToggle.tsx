import { useLayoutEffect, useState } from "react";

type Theme = "dark" | "light";

const STORAGE_KEY = "pokearena-modo";

/* El almacenamiento puede estar bloqueado por el navegador: el modo claro es el respaldo. */
function readSavedTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function saveTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Sin almacenamiento, el tema dura hasta recargar la página.
  }
}

/* Cambia entre el tema oscuro y el claro, y recuerda la elección. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readSavedTheme);

  // Antes de pintar, para que el modo guardado no parpadee.
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label="Cambiar modo oscuro/claro"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {/* El texto indica el modo al que se pasa al presionar, no el actual. */}
      {theme === "dark" ? "Modo Claro" : "Modo Oscuro"}
    </button>
  );
}
