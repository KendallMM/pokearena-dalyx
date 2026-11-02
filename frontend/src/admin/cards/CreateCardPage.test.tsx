import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ApiServicesProvider } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import { SessionProvider } from "../../session/SessionContext";
import { CREATED, fakeServices, pngFile, REFERENCES } from "../../test/fixtures";
import { FORBIDDEN_MESSAGE, NOT_AUTHENTICATED_MESSAGE } from "../accessMessages";
import { CreateCardPage } from "./CreateCardPage";

const GOOD_SIZE = async () => ({ width: 600, height: 840 });

function setup(
  services = fakeServices(),
  readImageSize: (file: File) => Promise<{ width: number; height: number }> = GOOD_SIZE,
) {
  const user = userEvent.setup();
  render(
    <SessionProvider>
      <ApiServicesProvider services={services}>
        <CreateCardPage readImageSize={readImageSize} />
      </ApiServicesProvider>
    </SessionProvider>,
  );
  return { user, services };
}

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("combobox", { name: /Tipo/ });
  await user.type(screen.getByLabelText(/Nombre/), "Charmander");
  await user.type(screen.getByLabelText(/Costo/), "3");
  await user.type(screen.getByLabelText(/Poder/), "-5");
  await user.selectOptions(screen.getByLabelText(/Tipo/), "FUE");
  await user.selectOptions(screen.getByLabelText(/Rareza/), "COMMON");
  await user.selectOptions(screen.getByLabelText(/Habilidad/), "HAB-000");
  await user.upload(screen.getByLabelText(/Imagen de la carta/), pngFile());
}

const submit = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole("button", { name: "Crear carta" }));

describe("CreateCardPage", () => {
  it("loads the options when it opens", async () => {
    const { services } = setup();
    expect(screen.getByText(/Cargando opciones/)).toBeInTheDocument();

    const types = await screen.findByRole("combobox", { name: /Tipo/ });
    expect(services.references.load).toHaveBeenCalledTimes(1);
    expect(types).toHaveTextContent("Fuego");
    expect(screen.getByLabelText(/Rareza/)).toHaveTextContent("Rara");
    expect(screen.getByLabelText(/Habilidad/)).toHaveTextContent(
      "Marea (HAB-001) · afecta a Agua",
    );
  });

  it("shows a retry when the options cannot be loaded", async () => {
    const services = fakeServices();
    services.references.load
      .mockRejectedValueOnce(new ApiError(0, "network", "sin red"))
      .mockResolvedValueOnce(REFERENCES);
    const { user } = setup(services);

    expect(
      await screen.findByText(/No se pudieron cargar las opciones/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("combobox", { name: /Tipo/ })).toBeInTheDocument();
  });

  it("explains a 403 when loading the options", async () => {
    const services = fakeServices();
    services.references.load.mockRejectedValue(new ApiError(403, "forbidden", "x"));
    setup(services);
    expect(await screen.findByText(FORBIDDEN_MESSAGE)).toBeInTheDocument();
  });

  it("blocks the submit and lists what is missing", async () => {
    const { user, services } = setup();
    await screen.findByRole("combobox", { name: /Tipo/ });
    await submit(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Revisa estos datos");
    expect(alert).toHaveTextContent(/Nombre: .*obligatorio/);
    expect(alert).toHaveTextContent(/Habilidad: .*Sin Habilidad/);
    expect(services.cards.create).not.toHaveBeenCalled();
    await waitFor(() => expect(alert).toHaveFocus());
    expect(screen.getByLabelText(/Nombre/)).toHaveAttribute("aria-invalid", "true");
  });

  it("rejects an image with a wrong ratio before sending", async () => {
    const { user, services } = setup(fakeServices(), async () => ({
      width: 840,
      height: 600,
    }));
    await fillValid(user);
    expect(
      await screen.findByText(/proporción 5:7/, { selector: "p.field__error, p" }),
    ).toBeInTheDocument();

    await submit(user);
    expect(services.cards.create).not.toHaveBeenCalled();
  });

  it("sends the card with the operation key and shows the code", async () => {
    const { user, services } = setup();
    await fillValid(user);
    await submit(user);

    expect(await screen.findByText("PKA-FUE-001")).toBeInTheDocument();
    expect(screen.getByText("Carta en proceso")).toBeInTheDocument();

    const [input, key] = services.cards.create.mock.calls[0]!;
    expect(input).toMatchObject({
      name: "Charmander",
      cost: 3,
      power: -5,
      cardType: "FUE",
      rarity: "COMMON",
      ability: "HAB-000",
    });
    expect(typeof key).toBe("string");
    expect(key.length).toBeGreaterThan(8);
  });

  it("tells the admin when the card already existed", async () => {
    const services = fakeServices();
    services.cards.create.mockResolvedValue({ ...CREATED, replayed: true });
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);
    expect(await screen.findByText(/ya estaba registrada/)).toBeInTheDocument();
  });

  it("lets the admin create another card with an empty form", async () => {
    const { user } = setup();
    await fillValid(user);
    await submit(user);
    await user.click(await screen.findByRole("button", { name: "Crear otra carta" }));

    expect(screen.getByLabelText(/Nombre/)).toHaveValue("");
    await fillValid(user);
    await submit(user);
  });

  it("uses a new key for each new card", async () => {
    const { user, services } = setup();
    await fillValid(user);
    await submit(user);
    await user.click(await screen.findByRole("button", { name: "Crear otra carta" }));
    await fillValid(user);
    await submit(user);
    await waitFor(() => expect(services.cards.create).toHaveBeenCalledTimes(2));

    const [first, second] = services.cards.create.mock.calls.map((call) => call[1]);
    expect(first).not.toBe(second);
  });

  it("puts a server field error under that field", async () => {
    const services = fakeServices();
    services.cards.create.mockRejectedValue(
      new ApiError(400, "validation_failed", "El nombre ya existe", "name"),
    );
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);

    const name = screen.getByLabelText(/Nombre/);
    await waitFor(() => expect(name).toHaveAttribute("aria-invalid", "true"));
    expect(screen.getAllByText(/El nombre ya existe/).length).toBeGreaterThan(0);
  });

  it("maps the card_type field of the API to the type select", async () => {
    const services = fakeServices();
    services.cards.create.mockRejectedValue(
      new ApiError(400, "validation_failed", "Tipo no válido", "card_type"),
    );
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);
    await waitFor(() =>
      expect(screen.getByLabelText(/Tipo/)).toHaveAttribute("aria-invalid", "true"),
    );
  });

  it.each([
    [401, NOT_AUTHENTICATED_MESSAGE],
    [403, FORBIDDEN_MESSAGE],
  ])("shows a different message for %i", async (status, message) => {
    const services = fakeServices();
    services.cards.create.mockRejectedValue(
      new ApiError(status, "x", "texto del servidor"),
    );
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText("texto del servidor")).not.toBeInTheDocument();
  });

  it("shows the server message on a 409", async () => {
    const services = fakeServices();
    services.cards.create.mockRejectedValue(
      new ApiError(409, "conflict", "Esa operación ya está en curso"),
    );
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);
    expect(
      await screen.findByText(/Esa operación ya está en curso/),
    ).toBeInTheDocument();
  });

  it("keeps the same key when retrying after a network failure", async () => {
    const services = fakeServices();
    services.cards.create
      .mockRejectedValueOnce(new ApiError(0, "network", "sin red"))
      .mockResolvedValueOnce(CREATED);
    const { user } = setup(services);
    await fillValid(user);

    await submit(user);
    expect(await screen.findByText(/no se duplicará/)).toBeInTheDocument();
    await submit(user);
    expect(await screen.findByText("PKA-FUE-001")).toBeInTheDocument();

    const keys = services.cards.create.mock.calls.map((call) => call[1]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
  });

  it("uses a new key when the form changes after a failure", async () => {
    const services = fakeServices();
    services.cards.create
      .mockRejectedValueOnce(new ApiError(500, "internal_error", "x"))
      .mockResolvedValueOnce(CREATED);
    const { user } = setup(services);
    await fillValid(user);

    await submit(user);
    await screen.findByText(/no se duplicará/);
    await user.type(screen.getByLabelText(/Nombre/), "x");
    await submit(user);
    await screen.findByText("PKA-FUE-001");

    const keys = services.cards.create.mock.calls.map((call) => call[1]);
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("disables the form while sending", async () => {
    const services = fakeServices();
    let finish: (value: typeof CREATED) => void = () => {};
    services.cards.create.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const { user } = setup(services);
    await fillValid(user);
    await submit(user);

    expect(await screen.findByRole("button", { name: /Creando carta/ })).toBeDisabled();
    expect(screen.getByLabelText(/Nombre/)).toBeDisabled();
    finish(CREATED);
    expect(await screen.findByText("PKA-FUE-001")).toBeInTheDocument();
  });
});
