import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { CreateCardPage } from "./admin/cards/CreateCardPage";
import { SearchCardsPage } from "./admin/cards/SearchCardsPage";
import { CreateLocationPage } from "./admin/locations/CreateLocationPage";
import { MainMenuPage } from "./admin/MainMenuPage";
import { LoginPage } from "./auth/LoginPage";
import { RequireAccount } from "./auth/RequireAccount";
import { MatchPage } from "./game/MatchPage";

/* Rutas de la aplicación. Cada pantalla nueva se agrega aquí. */
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAccount />}>
        <Route path="/partida" element={<MatchPage />} />
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
