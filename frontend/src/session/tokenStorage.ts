const KEY = "pokearena.session.token";

/**
 * La sesión vive en sessionStorage: se borra al cerrar la pestaña. Si el navegador
 * no permite el almacenamiento, la sesión dura mientras la página siga abierta.
 */
export function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string): void {
  try {
    window.sessionStorage.setItem(KEY, token);
  } catch {
    // Sin almacenamiento: queda solo en memoria.
  }
}

export function removeToken(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Nada que borrar.
  }
}
