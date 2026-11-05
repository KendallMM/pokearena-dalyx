import { forwardRef, type ReactNode } from "react";

interface Props {
  variant: "error" | "success" | "info";
  title?: string;
  children?: ReactNode;
}

/** Mensaje destacado. Los errores se anuncian de inmediato a los lectores de pantalla. */
export const Alert = forwardRef<HTMLDivElement, Props>(function Alert(
  { variant, title, children },
  ref,
) {
  return (
    <div
      ref={ref}
      tabIndex={-1}
      className={`alert alert--${variant}`}
      role={variant === "error" ? "alert" : "status"}
    >
      {title && <p className="alert__title">{title}</p>}
      {children}
    </div>
  );
});
