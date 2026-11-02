import { describe, expect, it, vi } from "vitest";

import { ApiError } from "./errors";
import { createHttpClient } from "./httpClient";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function clientWith(fetchFn: typeof fetch, token: string | null = "abc") {
  return createHttpClient({ baseUrl: "/api", getToken: () => token, fetchFn });
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error("Se esperaba un error");
}

describe("createHttpClient", () => {
  it("sends the session token and the base path", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    await clientWith(fetchFn).getCached("/admin/referencias");

    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe("/api/admin/referencias");
    expect(init.headers.Authorization).toBe("Bearer abc");
  });

  it("does not send Authorization when there is no session", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({}));
    await clientWith(fetchFn, null).getCached("/x");
    expect(fetchFn.mock.calls[0]![1].headers.Authorization).toBeUndefined();
  });

  it("reuses the stored response when the server answers 304", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ value: 1 }, { headers: { ETag: '"v1"' } }))
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    const client = clientWith(fetchFn);

    const first = await client.getCached("/admin/referencias");
    const second = await client.getCached("/admin/referencias");

    expect(second).toEqual(first);
    expect(fetchFn.mock.calls[0]![1].headers["If-None-Match"]).toBeUndefined();
    expect(fetchFn.mock.calls[1]![1].headers["If-None-Match"]).toBe('"v1"');
  });

  it("replaces the stored response when the content changes", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ value: 1 }, { headers: { ETag: '"v1"' } }))
      .mockResolvedValueOnce(jsonResponse({ value: 2 }, { headers: { ETag: '"v2"' } }))
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    const client = clientWith(fetchFn);

    await client.getCached("/p");
    await client.getCached("/p");
    expect(await client.getCached("/p")).toEqual({ value: 2 });
    expect(fetchFn.mock.calls[2]![1].headers["If-None-Match"]).toBe('"v2"');
  });

  it("turns the server error format into an ApiError", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          code: "validation_failed",
          message: "Costo inválido",
          field: "cost",
          correlation_id: "c-1",
        },
        { status: 400 },
      ),
    );
    const error = await failure(
      clientWith(fetchFn).postForm("/admin/cartas", new FormData()),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 400,
      code: "validation_failed",
      message: "Costo inválido",
      field: "cost",
      correlationId: "c-1",
    });
  });

  it("tells 401 and 403 apart", async () => {
    const make = (status: number) =>
      failure(
        clientWith(
          vi
            .fn()
            .mockResolvedValue(
              jsonResponse({ code: "x", message: "m", field: null }, { status }),
            ),
        ).getCached("/x"),
      );

    const unauthenticated = await make(401);
    const forbidden = await make(403);
    expect(unauthenticated.isNotAuthenticated).toBe(true);
    expect(unauthenticated.isForbidden).toBe(false);
    expect(forbidden.isForbidden).toBe(true);
    expect(forbidden.isNotAuthenticated).toBe(false);
  });

  it("uses a generic message when the error body is not JSON", async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response("<html>", { status: 502 }));
    const error = await failure(clientWith(fetchFn).getCached("/x"));
    expect(error.status).toBe(502);
    expect(error.isServerError).toBe(true);
    expect(error.message).toMatch(/inesperado/);
  });

  it("reports a network failure as an ApiError with status 0", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await failure(clientWith(fetchFn).getCached("/x"));
    expect(error.isNetworkError).toBe(true);
    expect(error.message).toMatch(/No se pudo conectar/);
  });

  it("posts a form with the extra headers and without forcing Content-Type", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(jsonResponse({ code: "A" }, { status: 202 }));
    const form = new FormData();
    form.append("name", "x");
    const response = await clientWith(fetchFn).postForm("/admin/cartas", form, {
      "Idempotency-Key": "key-1",
    });

    const init = fetchFn.mock.calls[0]![1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(form);
    expect(init.headers["Idempotency-Key"]).toBe("key-1");
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(response.status).toBe(202);
  });
});
