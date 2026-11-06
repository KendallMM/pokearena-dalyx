import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiServicesProvider } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import { AccountProvider } from "../session/AccountContext";
import { SessionProvider, useSession } from "../session/SessionContext";
import { fakeServices } from "../test/fixtures";
import { GoogleLoginCancelled, requestGoogleIdentity } from "./googleSignIn";
import { LoginPage } from "./LoginPage";

vi.mock("./googleSignIn", async (importOriginal) => ({
  ...(await importOriginal()),
  requestGoogleIdentity: vi.fn(),
}));

function ProtectedPage() {
  const { getToken } = useSession();
  return <p>Juego: {getToken()}</p>;
}

function setup() {
  const services = fakeServices();
  services.sessions.challenge.mockResolvedValue({
    client_id: "client",
    nonce: "one-time",
    expires_in: 300,
  });
  services.sessions.signInGoogle.mockResolvedValue({
    access_token: "pokearena-token",
    token_type: "Bearer",
    expires_in: 900,
    expires_at: new Date(Date.now() + 900_000).toISOString(),
    player: {
      id: "player",
      name: "Jugador",
      email: "p@example.test",
      role: "player",
      elo: 0,
      cubes: 100,
    },
    initial_collection: { status: "delivered", message: "Colección entregada" },
  });
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <SessionProvider>
        <AccountProvider>
          <ApiServicesProvider services={services}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/partida" element={<ProtectedPage />} />
            </Routes>
          </ApiServicesProvider>
        </AccountProvider>
      </SessionProvider>
    </MemoryRouter>,
  );
  return services;
}

describe("Google login", () => {
  beforeEach(() => {
    vi.spyOn(window, "open").mockReturnValue({ close: vi.fn() });
    vi.mocked(requestGoogleIdentity).mockReset();
    vi.mocked(requestGoogleIdentity).mockResolvedValue("google-identity-token");
  });
  afterEach(() => vi.restoreAllMocks());

  it("exchanges Google's token and enters the game with only the internal token", async () => {
    const services = setup();
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión con Google" }));
    expect(await screen.findByText("Juego: pokearena-token")).toBeInTheDocument();
    expect(services.sessions.signInGoogle).toHaveBeenCalledWith(
      "google-identity-token",
    );
    expect(sessionStorage.getItem("pokearena.session.token")).toBeNull();
    expect(localStorage.getItem("pokearena.session.token")).toBeNull();
    expect(screen.queryByLabelText("Contraseña")).not.toBeInTheDocument();
  });

  it("shows cancellation without creating any internal session", async () => {
    vi.mocked(requestGoogleIdentity).mockRejectedValue(new GoogleLoginCancelled());
    const services = setup();
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión con Google" }));
    expect(await screen.findByText("Inicio de sesión cancelado")).toBeInTheDocument();
    expect(services.sessions.signInGoogle).not.toHaveBeenCalled();
    expect(screen.queryByText(/Juego:/)).not.toBeInTheDocument();
  });

  it.each([401, 503])("shows HTTP %i with its correlation ID", async (status) => {
    const services = setup();
    services.sessions.signInGoogle.mockRejectedValue(
      new ApiError(status, "error", "Google no está disponible.", null, "request-123"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión con Google" }));
    expect(await screen.findByText(/Referencia: request-123/)).toBeInTheDocument();
    if (status === 401)
      expect(screen.getByText(/Inicia sesión con Google de nuevo/)).toBeInTheDocument();
    else expect(screen.getByText(/Google no está disponible/)).toBeInTheDocument();
    expect(screen.queryByText(/Juego:/)).not.toBeInTheDocument();
  });

  it("does not contact the backend when the browser blocks the popup", async () => {
    vi.mocked(window.open).mockReturnValue(null);
    const services = setup();
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión con Google" }));
    expect(screen.getByText(/Permite las ventanas emergentes/)).toBeInTheDocument();
    await waitFor(() => expect(services.sessions.challenge).not.toHaveBeenCalled());
  });
});
