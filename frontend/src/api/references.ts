import type { HttpClient } from "./httpClient";
import type { References } from "./types";

export interface ReferencesApi {
  /** Carga los valores que se pueden elegir en los formularios de contenido. */
  load(): Promise<References>;
}

export function createReferencesApi(http: HttpClient): ReferencesApi {
  return {
    load: () => http.getCached<References>("/admin/referencias"),
  };
}
