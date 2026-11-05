import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
  /** Mientras es verdadero el botón no se puede usar de nuevo (evita doble envío). */
  busy?: boolean;
}

export function Button({
  variant = "primary",
  busy = false,
  disabled,
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      className={`button button--${variant}`}
      disabled={disabled || busy}
      aria-busy={busy}
    >
      {children}
    </button>
  );
}
