import { describe, expect, it, vi } from "vitest";

import { createHttpClient } from "./httpClient";
import { createSessionsApi } from "./sessions";

describe("session API", () => {
  it("exchanges Google identity as JSON, then sends only Poké-Arena credentials", async () => {
    let token = null;
    const fetchFn = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
    const api = createSessionsApi(createHttpClient({ getToken: () => token, fetchFn }));
    await api.challenge();
    await api.signInGoogle("google-token");
    expect(fetchFn.mock.calls[1][0]).toBe("/api/v1/sesiones/google");
    expect(JSON.parse(fetchFn.mock.calls[1][1].body)).toEqual({
      credential: "google-token",
    });
    expect(fetchFn.mock.calls[1][1].headers.Authorization).toBeUndefined();
    token = "pokearena-token";
    await api.me();
    expect(fetchFn.mock.calls[2][1].headers.Authorization).toBe(
      "Bearer pokearena-token",
    );
  });
});
