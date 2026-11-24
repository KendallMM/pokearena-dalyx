import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ApiServicesProvider } from "../api/ApiContext";
import { ApiError } from "../api/errors";
import type { MatchSearch } from "../api/searches";
import { fakeServices } from "../test/fixtures";
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

function setup() {
  const services = fakeServices();
  services.decks.list.mockResolvedValue([{ id: "deck-1", name: "Llamas", cards: [] }]);
  render(
    <MemoryRouter>
      <ApiServicesProvider services={services}>
        <RankedSearch />
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
  vi.mocked(api.get).mockResolvedValue({
    ...waiting,
    status: "found",
    match_id: "match-1",
  });
  const select = await screen.findByLabelText("Deck");
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
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(api.get).toHaveBeenCalledWith("search-1");
  expect(screen.getByText("Partida encontrada: match-1")).toBeVisible();
  expect(screen.queryByLabelText("Deck")).not.toBeInTheDocument();
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
});
