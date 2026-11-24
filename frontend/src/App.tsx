import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { CreateCardPage } from "./admin/cards/CreateCardPage";
import { SearchCardsPage } from "./admin/cards/SearchCardsPage";
import { CreateLocationPage } from "./admin/locations/CreateLocationPage";
import { MainMenuPage } from "./admin/MainMenuPage";
import { LoginPage } from "./auth/LoginPage";
import { RequireAccount } from "./auth/RequireAccount";
import { PlayerGamePage } from "./game/PlayerGamePage";
import { AssignedMatchPage } from "./game/AssignedMatchPage";
import { CatalogPage } from "./player/catalog/CatalogPage";
import { CreateDeckPage } from "./player/decks/CreateDeckPage";
import { DeckDetailPage } from "./player/decks/DeckDetailPage";
import { DecksPage } from "./player/decks/DecksPage";
import { PlayerLayout } from "./player/PlayerLayout";
import { GoogleCallbackPage } from "./auth/GoogleCallbackPage";

/* Rutas de la aplicación. Cada pantalla nueva se agrega aquí. */
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />
      <Route element={<RequireAccount />}>
        <Route element={<PlayerLayout />}>
          <Route path="/partida" element={<PlayerGamePage />} />
          <Route path="/partida/:matchId" element={<AssignedMatchPage />} />
          <Route path="/catalogo" element={<CatalogPage />} />
          <Route path="/mazos" element={<DecksPage />} />
          <Route path="/mazos/nuevo" element={<CreateDeckPage />} />
          <Route path="/mazos/:deckId" element={<DeckDetailPage />} />
        </Route>
        <Route element={<AdminLayout />}>
          <Route path="/menu" element={<MainMenuPage />} />
          <Route path="/admin/cartas" element={<SearchCardsPage />} />
          <Route path="/admin/cartas/nueva" element={<CreateCardPage />} />
          <Route path="/admin/ubicaciones/nueva" element={<CreateLocationPage />} />
          <Route path="*" element={<Navigate to="/menu" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
