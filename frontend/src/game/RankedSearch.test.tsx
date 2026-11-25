import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ApiServicesProvider } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { MatchSearch } from "../api/searches";
import { fakeServices } from "../test/fixtures";
import { AssignedMatchPage } from "./AssignedMatchPage";
import { RankedSearch } from "./RankedSearch";

const waiting: MatchSearch = {
  id: "search-1",
  deck_id: "deck-1",
  mode: "ranked",
  status: "waiting",
  created_at: "2026-01-01T00:00:00Z",
  match_id: null,
  error: null,
};

function Location() {
  return <output aria-label="Ruta actual">{useLocation().pathname}</output>;
}

function setup(current?: MatchSearch) {
  const services = fakeServices();
  if (current) vi.mocked(services.searches.current).mockResolvedValue(current);
  services.decks.list.mockResolvedValue([{ id: "deck-1", name: "Llamas", cards: [] }]);
  render(
    <MemoryRouter>
      <ApiServicesProvider services={services}>
        <Routes>
          <Route path="/partida/:matchId" element={<AssignedMatchPage />} />
          <Route path="*" element={<RankedSearch />} />
        </Routes>
        <Location />
      </ApiServicesProvider>
    </MemoryRouter>,
  );
  return services.searches;
}

afterEach(() => vi.useRealTimers());

it("envía un solo ingreso, consulta el resultado y mantiene fijo el deck", async () => {
  const api = setup();
  let accept!: (search: MatchSearch) => void;
  vi.mocked(api.enter).mockReturnValue(
    new Promise((resolve) => {
      accept = resolve;
    }),
  );
  vi.mocked(api.current).mockResolvedValue({
    ...waiting,
    status: "found",
    match_id: "match-1",
  });
  const select = await screen.findByLabelText("Deck");
  expect(screen.getByText("No tienes una búsqueda de partida")).toBeVisible();
  const button = screen.getByRole("button", { name: "Buscar partida" });
  fireEvent.change(select, { target: { value: "deck-1" } });
  fireEvent.click(button);
  fireEvent.click(button);
  expect(api.enter).toHaveBeenCalledTimes(1);
  expect(api.enter).toHaveBeenCalledWith("deck-1", expect.any(String));
  vi.useFakeTimers();
  await act(async () => {
    accept(waiting);
  });
  expect(screen.getByText("Buscando rival")).toBeVisible();
  expect(screen.queryByLabelText("Deck")).not.toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  vi.useRealTimers();
  expect(await screen.findByText("Partida encontrada: match-1")).toBeVisible();
  expect(api.current).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("region", { name: "Montaña" })).toBeVisible();
  expect(screen.getByRole("region", { name: "Bosque" })).toBeVisible();
  expect(screen.getByRole("region", { name: "Lago" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Carta propia" })).toBeVisible();
  expect(screen.getByText("Planta")).toBeVisible();
  expect(screen.getByText("Común")).toBeVisible();
  expect(screen.getByText("Sin Habilidad")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Ruta actual")).toHaveTextContent("/partida/match-1");
  expect(screen.queryByLabelText("Deck")).not.toBeInTheDocument();
});

it("muestra la oferta del servidor y repite la misma clave si falla al aceptarla", async () => {
  const api = setup({ ...waiting, wait_seconds: 60, bot_available: true });
  vi.mocked(api.acceptBot)
    .mockRejectedValueOnce(new ApiError(503, "service_unavailable", "Reintenta."))
    .mockResolvedValueOnce({ match_id: "partida-bot" });
  expect(await screen.findByText("1:00")).toBeVisible();
  const accept = screen.getByRole("button", { name: "Jugar contra el bot" });
  fireEvent.click(accept);
  expect(await screen.findByText("Reintenta.")).toBeVisible();
  fireEvent.click(accept);
  await waitFor(() =>
    expect(screen.getByLabelText("Ruta actual")).toHaveTextContent(
      "/partida/partida-bot",
    ),
  );
  const calls = vi.mocked(api.acceptBot).mock.calls;
  expect(calls[0]).toEqual(["search-1", expect.any(String)]);
  expect(calls[0]).toEqual(calls[1]);
});

it("muestra el saldo del servidor y conserva la clave de una solicitud reintentada", async () => {
  const api = setup();
  vi.mocked(api.enter)
    .mockRejectedValueOnce(
      new ApiError(
        400,
        "validation_failed",
        "Tienes 7 cubos. Compra cubos para continuar.",
      ),
    )
    .mockResolvedValueOnce(waiting);
  fireEvent.change(await screen.findByLabelText("Deck"), {
    target: { value: "deck-1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Buscar partida" }));
  expect(
    await screen.findByText("Tienes 7 cubos. Compra cubos para continuar."),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Buscar partida" }));
  await screen.findByText("Buscando rival");
  expect(vi.mocked(api.enter).mock.calls[0]).toEqual(
    vi.mocked(api.enter).mock.calls[1],
  );
  vi.mocked(api.cancel).mockResolvedValue({ ...waiting, status: "cancelled" });
  fireEvent.click(screen.getByRole("button", { name: "Salir de la búsqueda" }));
  await waitFor(() => expect(screen.getByLabelText("Deck")).toBeVisible());
  expect(api.cancel).toHaveBeenCalledWith("search-1");
  expect(screen.getByText("Búsqueda cancelada")).toBeVisible();
});

it("conserva el conflicto de cancelación al abrir la partida asignada", async () => {
  const api = setup(waiting);
  vi.mocked(api.cancel).mockRejectedValue(
    new ApiError(
      409,
      "conflict",
      "La búsqueda ya encontró la partida match-1.",
      "match_id",
    ),
  );
  const cancel = await screen.findByRole("button", { name: "Salir de la búsqueda" });
  vi.mocked(api.current).mockResolvedValue({
    ...waiting,
    status: "found",
    match_id: "match-1",
  });
  fireEvent.click(cancel);
  expect(
    await screen.findByRole("heading", { name: "Partida asignada" }),
  ).toBeVisible();
  expect(await screen.findByText("No se pudo cancelar la búsqueda")).toBeVisible();
  expect(screen.getByText("La búsqueda ya encontró la partida match-1.")).toBeVisible();
});

it("distingue al salir de una búsqueda que ya había terminado", async () => {
  const api = setup(waiting);
  vi.mocked(api.cancel).mockResolvedValue({
    ...waiting,
    status: "expired",
    already_ended: true,
  });
  fireEvent.click(await screen.findByRole("button", { name: "Salir de la búsqueda" }));
  expect(await screen.findByText("La búsqueda ya había terminado")).toBeVisible();
  expect(screen.getByText("Expirada por inactividad.")).toBeVisible();
});

it("conserva el conflicto del bot al abrir la partida asignada", async () => {
  const api = setup({ ...waiting, bot_available: true });
  vi.mocked(api.acceptBot).mockRejectedValue(
    new ApiError(
      409,
      "conflict",
      "La búsqueda ya encontró la partida match-1.",
      "match_id",
    ),
  );
  const accept = await screen.findByRole("button", { name: "Jugar contra el bot" });
  vi.mocked(api.current).mockResolvedValue({
    ...waiting,
    status: "found",
    match_id: "match-1",
  });
  fireEvent.click(accept);
  expect(await screen.findByText("No se pudo aceptar la oferta del bot")).toBeVisible();
  expect(screen.getByText("La búsqueda ya encontró la partida match-1.")).toBeVisible();
});
