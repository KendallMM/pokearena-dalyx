import type { HttpClient } from "./httpClient";

export interface InitialMatch {
  id: string;
  mode: "ranked" | "bot" | "tournament";
  turn: number;
  total_turns: number;
  turn_seconds: number;
  deadline: string;
  remaining_ms: number;
  energy: number;
  stake: number | null;
  locations: { id: number; name: string; description: string; has_image?: boolean }[];
  hand: {
    name: string;
    cost: number;
    power: number;
    code?: string | null;
    type?: string | null;
    type_name?: string | null;
    rarity?: string | null;
    rarity_name?: string | null;
    ability_name?: string | null;
  }[];
}

export function createMatchesApi(http: HttpClient) {
  return {
    initial: (id: string) =>
      http.getJson<InitialMatch>(`/v1/partidas/${encodeURIComponent(id)}`, "no-store"),
    locationImage: (id: string, locationId: number) =>
      http.getBlob(
        `/v1/partidas/${encodeURIComponent(id)}/ubicaciones/${locationId}/imagen`,
      ),
  };
}
