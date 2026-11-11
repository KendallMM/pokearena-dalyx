import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiServicesProvider } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import type { PlayerCatalogCard } from "../../api/types";
import { fakeServices } from "../../test/fixtures";
import { CatalogPage, PLAYERS_ONLY_MESSAGE } from "./CatalogPage";

function card(code: string, copies: number, name = code): PlayerCatalogCard {
  return {
    code,
    name,
    cost: 2,
    power: 3,
    card_type: { code: "FUE", name: "Fuego" },
    rarity: { code: "COMMON", name: "Común" },
    ability: { code: "HAB-000", name: "Sin Habilidad", affected_card_type: null },
    image_url: `/v1/cartas/${code}/imagen`,
    owned: copies > 0,
    copies,
  };
}

function setup(services = fakeServices()) {
  const user = userEvent.setup();
  render(
    <ApiServicesProvider services={services}>
      <MemoryRouter>
        <CatalogPage />
      </MemoryRouter>
    </ApiServicesProvider>,
  );
  return { user, services };
}

describe("CatalogPage", () => {
  it("shows every card with how many copies the player owns", async () => {
    const services = fakeServices();
    services.playerCatalog.search.mockResolvedValue({
      items: [card("PKA-FUE-001", 2, "Charmander"), card("PKA-FUE-002", 0, "Vulpix")],
      next_cursor: null,
    });
    setup(services);

    const owned = (await screen.findByText("Charmander")).closest("li")!;
    expect(within(owned).getByText("Tienes 2 copias")).toBeInTheDocument();
    const missing = screen.getByText("Vulpix").closest("li")!;
    expect(within(missing).getByText("No la tienes")).toBeInTheDocument();
    expect(services.playerCatalog.image).toHaveBeenCalledWith(
      "/v1/cartas/PKA-FUE-001/imagen",
    );
  });

  it("combines type, cost and owned-only filters", async () => {
    const { user, services } = setup();
    await screen.findByRole("combobox", { name: /Tipo/ });
    await user.selectOptions(screen.getByLabelText(/Tipo/), "AGU");
    await user.type(screen.getByLabelText(/Costo mínimo/), "2");
    await user.type(screen.getByLabelText(/Costo máximo/), "4");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() =>
      expect(services.playerCatalog.search).toHaveBeenLastCalledWith(
        { cardType: "AGU", costMin: 2, costMax: 4, ownedOnly: undefined },
        null,
      ),
    );

    await user.click(screen.getByLabelText("Ver solo mis cartas"));
    await waitFor(() =>
      expect(services.playerCatalog.search).toHaveBeenLastCalledWith(
        { cardType: "AGU", costMin: 2, costMax: 4, ownedOnly: true },
        null,
      ),
    );
    expect(
      await screen.findByText("No tienes cartas con esos filtros."),
    ).toBeInTheDocument();
  });

  it("loads the next page with the cursor", async () => {
    const services = fakeServices();
    services.playerCatalog.search
      .mockResolvedValueOnce({ items: [card("A", 1)], next_cursor: 7 })
      .mockResolvedValueOnce({ items: [card("B", 0)], next_cursor: null });
    const { user } = setup(services);

    await user.click(await screen.findByRole("button", { name: "Cargar más" }));
    expect(await screen.findByText("B")).toBeInTheDocument();
    expect(services.playerCatalog.search).toHaveBeenLastCalledWith({}, 7);
    expect(
      screen.queryByRole("button", { name: "Cargar más" }),
    ).not.toBeInTheDocument();
  });

  it("checks the cost range before asking the server", async () => {
    const { user, services } = setup();
    await screen.findByRole("combobox", { name: /Tipo/ });
    await user.type(screen.getByLabelText(/Costo mínimo/), "11");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    expect(
      await screen.findByText("El costo mínimo debe estar entre 0 y 10."),
    ).toBeInTheDocument();
    expect(services.playerCatalog.search).toHaveBeenCalledTimes(1);
  });

  it("shows the server message under the filter it rejected", async () => {
    const services = fakeServices();
    services.playerCatalog.search.mockRejectedValue(
      new ApiError(
        400,
        "validation_failed",
        "El tipo de carta no existe. Valores permitidos: FUE, AGU.",
        "card_type",
      ),
    );
    setup(services);
    expect(
      await screen.findByText(
        "El tipo de carta no existe. Valores permitidos: FUE, AGU.",
      ),
    ).toBeInTheDocument();
  });

  it("explains that the catalog is for player accounts", async () => {
    const services = fakeServices();
    services.playerCatalog.references.mockRejectedValue(
      new ApiError(403, "permission_denied", "x"),
    );
    setup(services);
    expect(await screen.findByText(PLAYERS_ONLY_MESSAGE)).toBeInTheDocument();
  });
});
