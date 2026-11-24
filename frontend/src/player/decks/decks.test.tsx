import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiServicesProvider } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import type { DeckCard, PlayerCatalogCard } from "../../api/types";
import { fakeServices } from "../../test/fixtures";
import { CreateDeckPage } from "./CreateDeckPage";
import { DeckDetailPage } from "./DeckDetailPage";
import { DecksPage } from "./DecksPage";

function card(index: number): PlayerCatalogCard {
  const code = `PKA-FUE-${String(index).padStart(3, "0")}`;
  return {
    code,
    name: `Carta ${index}`,
    cost: 1,
    power: 2,
    card_type: { code: "FUE", name: "Fuego" },
    rarity: { code: "COMMON", name: "Común" },
    ability: { code: "HAB-000", name: "Sin Habilidad", affected_card_type: null },
    image_url: `/v1/cartas/${code}/imagen`,
    owned: true,
    copies: 1,
  };
}

const COLLECTION = Array.from({ length: 15 }, (_, index) => card(index + 1));

function setup(services: ReturnType<typeof fakeServices>, path: string) {
  const user = userEvent.setup();
  render(
    <ApiServicesProvider services={services}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/mazos" element={<DecksPage />} />
          <Route path="/mazos/nuevo" element={<CreateDeckPage />} />
          <Route path="/mazos/:deckId" element={<DeckDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ApiServicesProvider>,
  );
  return user;
}

function withCollection() {
  const services = fakeServices();
  services.playerCatalog.search.mockResolvedValue({
    items: COLLECTION,
    next_cursor: null,
  });
  return services;
}

async function pick(user: ReturnType<typeof userEvent.setup>, count: number) {
  await screen.findByLabelText("Elegir Carta 1");
  for (let index = 1; index <= count; index += 1) {
    await user.click(screen.getByLabelText(`Elegir Carta ${index}`));
  }
}

describe("Decks", () => {
  it("lists my decks", async () => {
    const services = fakeServices();
    services.decks.list.mockResolvedValue([
      { id: "d1", name: "Fuego", cards: COLLECTION.slice(0, 12) as DeckCard[] },
    ]);
    setup(services, "/mazos");
    expect(await screen.findByText("Fuego")).toBeInTheDocument();
    expect(screen.getByText("12 cartas")).toBeInTheDocument();
  });

  it("explains when there are no decks", async () => {
    setup(fakeServices(), "/mazos");
    expect(await screen.findByText("Aún no tienes decks")).toBeInTheDocument();
  });

  it("shows not found for a foreign deck", async () => {
    const services = fakeServices();
    services.decks.get.mockRejectedValue(
      new ApiError(404, "not_found", "El deck no existe."),
    );
    setup(services, "/mazos/otro");
    expect(await screen.findByText("El deck no existe.")).toBeInTheDocument();
  });

  it("creates a deck from my collection", async () => {
    const services = withCollection();
    services.decks.get.mockResolvedValue({ id: "deck-1", name: "Deck", cards: [] });
    const user = setup(services, "/mazos/nuevo");
    expect(services.playerCatalog.search).toHaveBeenCalledWith(
      { ownedOnly: true },
      null,
    );
    await pick(user, 12);
    expect(screen.getByText("12 de 12 cartas elegidas")).toBeInTheDocument();
    expect(screen.getByLabelText("Elegir Carta 13")).toBeDisabled();
    await user.type(screen.getByLabelText(/Nombre del deck/), "Mi deck");
    await user.click(screen.getByRole("button", { name: "Guardar deck" }));
    await waitFor(() => expect(services.decks.create).toHaveBeenCalledTimes(1));
    const [name, cards, key] = services.decks.create.mock.calls[0]!;
    expect(name).toBe("Mi deck");
    expect(cards).toEqual(COLLECTION.slice(0, 12).map((c) => c.code));
    expect(key).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Deck" })).toBeInTheDocument();
  });

  it("does not send a deck without 12 cards", async () => {
    const services = withCollection();
    const user = setup(services, "/mazos/nuevo");
    await pick(user, 3);
    await user.type(screen.getByLabelText(/Nombre del deck/), "Corto");
    await user.click(screen.getByRole("button", { name: "Guardar deck" }));
    expect(await screen.findByText(/llevas 3/)).toBeInTheDocument();
    expect(services.decks.create).not.toHaveBeenCalled();
  });

  it("reuses the operation key on a network retry", async () => {
    const services = withCollection();
    services.decks.create.mockRejectedValueOnce(new ApiError(0, "network_error", "x"));
    services.decks.get.mockResolvedValue({ id: "deck-1", name: "Deck", cards: [] });
    const user = setup(services, "/mazos/nuevo");
    await pick(user, 12);
    await user.type(screen.getByLabelText(/Nombre del deck/), "Mi deck");
    await user.click(screen.getByRole("button", { name: "Guardar deck" }));
    await screen.findByText(/No se pudo completar/);
    await user.click(screen.getByRole("button", { name: "Guardar deck" }));
    await waitFor(() => expect(services.decks.create).toHaveBeenCalledTimes(2));
    expect(services.decks.create.mock.calls[1]![2]).toBe(
      services.decks.create.mock.calls[0]![2],
    );
  });

  it("shows a repeated name under the name field", async () => {
    const services = withCollection();
    services.decks.create.mockRejectedValue(
      new ApiError(409, "conflict", 'Ya tienes un deck llamado "Mi deck".', "name"),
    );
    const user = setup(services, "/mazos/nuevo");
    await pick(user, 12);
    await user.type(screen.getByLabelText(/Nombre del deck/), "Mi deck");
    await user.click(screen.getByRole("button", { name: "Guardar deck" }));
    expect(await screen.findByText(/Ya tienes un deck llamado/)).toBeInTheDocument();
  });
});
