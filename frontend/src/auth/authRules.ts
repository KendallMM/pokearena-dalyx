export const PASSWORD_MIN_LENGTH = 8;
export const NAME_MAX_LENGTH = 60;

export type AuthMode = "login" | "register";

export interface AuthValues {
  name: string;
  email: string;
  password: string;
  confirmation: string;
}

export type AuthErrors = Partial<Record<keyof AuthValues, string>>;

export const EMPTY_AUTH_FORM: AuthValues = {
  name: "",
  email: "",
  password: "",
  confirmation: "",
};

/* Revisión básica del formato: algo@algo.algo */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateAuthValues(mode: AuthMode, values: AuthValues): AuthErrors {
  const errors: AuthErrors = {};

  if (!values.email.trim()) errors.email = "El correo es obligatorio.";
  else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = "Escribe un correo válido.";
  }

  if (!values.password) errors.password = "La contraseña es obligatoria.";

  if (mode === "register") {
    if (!values.name.trim()) errors.name = "El nombre es obligatorio.";
    if (values.password && values.password.length < PASSWORD_MIN_LENGTH) {
      errors.password = `La contraseña debe tener al menos ${PASSWORD_MIN_LENGTH} caracteres.`;
    }
    if (values.password !== values.confirmation) {
      errors.confirmation = "Las contraseñas no coinciden.";
    }
  }
  return errors;
}
