import { ApiError } from "./errors";
import type { ApiErrorBody } from "./types";

export interface HttpResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

export interface HttpClient {
  /** GET que reutiliza la respuesta guardada cuando el servidor responde 304 (ETag). */
  getCached<T>(path: string): Promise<T>;
  /** POST de un formulario con archivos. */
  postForm<T>(
    path: string,
    body: FormData,
    headers?: Record<string, string>,
  ): Promise<HttpResponse<T>>;
}

interface Options {
  /** Prefijo de todas las rutas. En desarrollo, Vite lo reenvía al backend. */
  baseUrl?: string;
  /** Token de la sesión actual, o null si no hay sesión. */
  getToken: () => string | null;
  fetchFn?: typeof fetch;
}

const NETWORK_MESSAGE =
  "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";

/**
 * Cliente HTTP único de la interfaz: agrega la sesión, traduce los errores del
 * servidor a ApiError y maneja las consultas con ETag.
 */
export function createHttpClient({
  baseUrl = "/api",
  getToken,
  fetchFn,
}: Options): HttpClient {
  // Se resuelve al usarse, para que las pruebas puedan reemplazar fetch.
  const doFetch = (input: string, init: RequestInit) => (fetchFn ?? fetch)(input, init);
  const etagCache = new Map<string, { etag: string; data: unknown }>();

  function authHeaders(): Record<string, string> {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function send(path: string, init: RequestInit): Promise<Response> {
    try {
      return await doFetch(`${baseUrl}${path}`, init);
    } catch {
      throw new ApiError(0, "network_error", NETWORK_MESSAGE);
    }
  }

  async function toError(response: Response): Promise<ApiError> {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await response.json()) as Partial<ApiErrorBody>;
    } catch {
      // El cuerpo no es JSON: se usa un mensaje genérico según el estado.
    }
    return new ApiError(
      response.status,
      body.code ?? "unknown_error",
      body.message ?? "Ocurrió un error inesperado. Inténtalo de nuevo.",
      body.field ?? null,
      body.correlation_id ?? null,
    );
  }

  return {
    async getCached<T>(path: string): Promise<T> {
      const cached = etagCache.get(path);
      const headers: Record<string, string> = { ...authHeaders() };
      if (cached) headers["If-None-Match"] = cached.etag;

      const response = await send(path, { method: "GET", headers });
      if (response.status === 304 && cached) return cached.data as T;
      if (!response.ok) throw await toError(response);

      const data = (await response.json()) as T;
      const etag = response.headers.get("ETag");
      if (etag) etagCache.set(path, { etag, data });
      return data;
    },

    async postForm<T>(
      path: string,
      body: FormData,
      headers: Record<string, string> = {},
    ): Promise<HttpResponse<T>> {
      // No se fija Content-Type: el navegador agrega el límite (boundary) del formulario.
      const response = await send(path, {
        method: "POST",
        body,
        headers: { ...authHeaders(), ...headers },
      });
      if (!response.ok) throw await toError(response);
      return {
        data: (await response.json()) as T,
        status: response.status,
        headers: response.headers,
      };
    },
  };
}
