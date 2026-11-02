import { describe, expect, it, vi } from "vitest";

import { createCardsApi } from "./cards";
import type { HttpClient } from "./httpClient";
import { pngFile } from "../test/fixtures";

function httpReturning(headers: Record<string, string> = {}) {
  const postForm = vi.fn().mockResolvedValue({
    data: {
      code: "PKA-FUE-001",
      status: "pending_thumbnail",
      message: "Carta en proceso",
    },
    status: 202,
    headers: new Headers(headers),
  });
  return { http: { postForm } as unknown as HttpClient, postForm };
}

const INPUT = {
  name: "Charmander",
  cost: 3,
  power: -5,
  cardType: "FUE",
  rarity: "COMMON",
  ability: "HAB-000",
  image: pngFile(),
};

describe("cards api", () => {
  it("sends the card as a form using the field names of the API", async () => {
    const { http, postForm } = httpReturning();
    await createCardsApi(http).create(INPUT, "key-1");

    const [path, form, headers] = postForm.mock.calls[0]!;
    expect(path).toBe("/admin/cartas");
    expect(Object.fromEntries((form as FormData).entries())).toMatchObject({
      name: "Charmander",
      cost: "3",
      power: "-5",
      card_type: "FUE",
      rarity: "COMMON",
      ability: "HAB-000",
    });
    expect((form as FormData).get("image")).toBeInstanceOf(File);
    expect(headers).toEqual({ "Idempotency-Key": "key-1" });
  });

  it("returns the code and marks a repeated operation", async () => {
    const first = await createCardsApi(httpReturning().http).create(INPUT, "k");
    const repeated = await createCardsApi(
      httpReturning({ "Idempotent-Replayed": "true" }).http,
    ).create(INPUT, "k");

    expect(first).toMatchObject({ code: "PKA-FUE-001", replayed: false });
    expect(repeated.replayed).toBe(true);
  });
});
