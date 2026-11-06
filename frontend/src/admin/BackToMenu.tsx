import { Link } from "react-router-dom";

/* Botón para volver al menú principal, a la derecha en la línea de acciones. */
export function BackToMenu() {
  return (
    <Link className="button button--secondary back-button" to="/menu">
      Regresar
    </Link>
  );
}
