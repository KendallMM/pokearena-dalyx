/** Error de una llamada a la API, con la forma única que devuelve el servidor. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field: string | null;
  readonly correlationId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    field: string | null = null,
    correlationId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
    this.correlationId = correlationId;
  }

  /** No hay sesión: el servidor no sabe quién es el usuario. */
  get isNotAuthenticated(): boolean {
    return this.status === 401;
  }

  /** Hay sesión, pero el usuario no tiene permiso para la operación. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** La llamada no llegó al servidor (sin red, servidor caído). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** Falla del servidor: conviene reintentar la misma operación. */
  get isServerError(): boolean {
    return this.status >= 500;
  }
}
