import { useState } from "react";
import { Navigate } from "react-router-dom";

import logo from "../../images/pokeball.png";
import { useApi } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import { useAccount } from "../session/AccountContext";
import { Alert, Button, ThemeToggle } from "../ui";
import { GoogleLoginCancelled, requestGoogleIdentity } from "./googleSignIn";

/** Entrada real con Google; las cuentas y permisos los determina el servidor. */
export function LoginPage() {
  const { account, enter } = useAccount();
  const { sessions } = useApi();
  const [message, setMessage] = useState(null);
  const [cancelled, setCancelled] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (account) {
    return <Navigate to={account.role === "player" ? "/partida" : "/menu"} replace />;
  }

  async function signIn() {
    // Se abre dentro del gesto del usuario para evitar el bloqueo de ventanas.
    const popup = window.open(
      "about:blank",
      "pokearena-google",
      "popup,width=500,height=650",
    );
    setMessage(null);
    setCancelled(false);
    if (!popup) {
      setMessage("Permite las ventanas emergentes para iniciar sesión con Google.");
      return;
    }
    setSubmitting(true);
    try {
      const challenge = await sessions.challenge();
      const credential = await requestGoogleIdentity(challenge, popup);
      enter(await sessions.signInGoogle(credential));
    } catch (error) {
      popup.close();
      setCancelled(error instanceof GoogleLoginCancelled);
      if (error instanceof ApiError) {
        const detail =
          error.status === 401
            ? "Tu identidad no pudo verificarse. Inicia sesión con Google de nuevo."
            : error.message;
        setMessage(
          error.correlationId ? `${detail} Referencia: ${error.correlationId}` : detail,
        );
      } else {
        setMessage(
          error instanceof Error
            ? error.message
            : "No se pudo iniciar sesión. Inténtalo de nuevo.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth__brand">
        <img className="auth__logo" src={logo} alt="" />
        <h1 className="auth__title">PokéArena</h1>
      </div>
      <h2>Iniciar sesión</h2>
      <p>Usa tu cuenta de Google para entrar a jugar.</p>
      {message && (
        <Alert
          variant={cancelled ? "info" : "error"}
          title={cancelled ? "Inicio de sesión cancelado" : "No se pudo continuar"}
        >
          <p>{message}</p>
        </Alert>
      )}
      <Button busy={submitting} onClick={() => void signIn()}>
        Iniciar sesión con Google
      </Button>
      <ThemeToggle />
    </main>
  );
}
