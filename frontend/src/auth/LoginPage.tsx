import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import logo from "../../images/pokeball.png";
import { useAccount } from "../session/AccountContext";
import { AccountError } from "../session/localAccounts";
import { Alert, Button, TextField, ThemeToggle } from "../ui";
import {
  EMPTY_AUTH_FORM,
  NAME_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  validateAuthValues,
  type AuthErrors,
  type AuthMode,
  type AuthValues,
} from "./authRules";

const UNEXPECTED_MESSAGE = "No se pudo completar la operación. Inténtalo de nuevo.";

/* Pantalla de entrada: iniciar sesión o crear una cuenta. */
export function LoginPage() {
  const { account, logIn, register } = useAccount();
  const [mode, setMode] = useState<AuthMode>("login");
  const [values, setValues] = useState<AuthValues>(EMPTY_AUTH_FORM);
  const [errors, setErrors] = useState<AuthErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (account) return <Navigate to="/menu" replace />;

  const registering = mode === "register";

  function changeMode(next: AuthMode) {
    setMode(next);
    setErrors({});
    setGeneralError(null);
    setValues((current) => ({ ...current, password: "", confirmation: "" }));
  }

  function change(field: keyof AuthValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setGeneralError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateAuthValues(mode, values);
    setErrors(found);
    setGeneralError(null);
    if (Object.values(found).some(Boolean)) return;

    setSubmitting(true);
    try {
      if (registering) {
        await register({
          name: values.name,
          email: values.email,
          password: values.password,
        });
      } else {
        await logIn(values.email, values.password);
      }
      // Con la cuenta lista, esta misma pantalla redirige al menú principal.
    } catch (error) {
      setGeneralError(
        error instanceof AccountError ? error.message : UNEXPECTED_MESSAGE,
      );
      setSubmitting(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth__brand">
        <img className="auth__logo" src={logo} alt="" />
        <h1 className="auth__title">PokéArena</h1>
      </div>

      <div className="auth__tabs">
        <button
          type="button"
          className="auth__tab"
          aria-pressed={!registering}
          onClick={() => changeMode("login")}
        >
          Iniciar sesión
        </button>
        <button
          type="button"
          className="auth__tab"
          aria-pressed={registering}
          onClick={() => changeMode("register")}
        >
          Registrarse
        </button>
      </div>

      <form className="form" onSubmit={(event) => void handleSubmit(event)} noValidate>
        {generalError && (
          <Alert variant="error" title="No se pudo continuar">
            <p>{generalError}</p>
          </Alert>
        )}
        {registering && (
          <TextField
            id="auth-name"
            label="Nombre"
            required
            autoComplete="name"
            maxLength={NAME_MAX_LENGTH}
            value={values.name}
            error={errors.name}
            disabled={submitting}
            onChange={(value) => change("name", value)}
          />
        )}
        <TextField
          id="auth-email"
          label="Correo"
          required
          type="email"
          autoComplete="email"
          value={values.email}
          error={errors.email}
          disabled={submitting}
          onChange={(value) => change("email", value)}
        />
        <TextField
          id="auth-password"
          label="Contraseña"
          required
          type="password"
          autoComplete={registering ? "new-password" : "current-password"}
          hint={registering ? `Al menos ${PASSWORD_MIN_LENGTH} caracteres.` : undefined}
          value={values.password}
          error={errors.password}
          disabled={submitting}
          onChange={(value) => change("password", value)}
        />
        {registering && (
          <TextField
            id="auth-confirmation"
            label="Repite la contraseña"
            required
            type="password"
            autoComplete="new-password"
            value={values.confirmation}
            error={errors.confirmation}
            disabled={submitting}
            onChange={(value) => change("confirmation", value)}
          />
        )}
        <div className="form__actions">
          <Button type="submit" busy={submitting}>
            {registering ? "Crear cuenta" : "Entrar"}
          </Button>
        </div>
        <p className="field__hint">
          Por ahora las cuentas se guardan solo en este navegador.
        </p>
      </form>
      <ThemeToggle />
    </main>
  );
}
