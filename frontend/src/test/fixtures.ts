import { vi } from "vitest";

import type { ApiServices } from "../api/ApiContext";
import type { CreateCardResult, CreateLocationResult, References } from "../api/types";

export const REFERENCES: References = {
  card_types: [
    { code: "FUE", name: "Fuego" },
    { code: "AGU", name: "Agua" },
  ],
  rarities: [
    { code: "COMMON", name: "Común" },
    { code: "RARE", name: "Rara" },
  ],
  abilities: [
    { code: "HAB-000", name: "Sin Habilidad", affected_card_type: null },
    { code: "HAB-001", name: "Marea", affected_card_type: "AGU" },
  ],
  location_effect_types: [],
};

export const CREATED: CreateCardResult = {
  code: "PKA-FUE-001",
  status: "pending_thumbnail",
  message: "Carta en proceso",
  replayed: false,
};

const LOCATION_CREATED: CreateLocationResult = {
  id: 41,
  status: "pending_thumbnail",
  message: "Ubicación en proceso",
  replayed: false,
};

/* Servicios falsos: cada prueba decide qué responden. */
export function fakeServices(): ApiServices & {
  references: { load: ReturnType<typeof vi.fn> };
  cards: { create: ReturnType<typeof vi.fn> };
  locations: { create: ReturnType<typeof vi.fn> };
  playerCatalog: {
    cardTypes: ReturnType<typeof vi.fn>;
    search: ReturnType<typeof vi.fn>;
    image: ReturnType<typeof vi.fn>;
  };
} {
  return {
    references: { load: vi.fn().mockResolvedValue(REFERENCES) },
    cards: {
      create: vi.fn().mockResolvedValue(CREATED),
      search: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
      image: vi.fn().mockResolvedValue(new Blob()),
    },
    locations: { create: vi.fn().mockResolvedValue(LOCATION_CREATED) },
    playerCatalog: {
      cardTypes: vi.fn().mockResolvedValue(REFERENCES.card_types),
      search: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
      image: vi.fn().mockResolvedValue(new Blob()),
    },
    sessions: { challenge: vi.fn(), signInGoogle: vi.fn(), me: vi.fn() },
  };
}

export function pngFile(name = "carta.png", type = "image/png", bytes = 100): File {
  return new File([new Uint8Array(bytes)], name, { type });
}
