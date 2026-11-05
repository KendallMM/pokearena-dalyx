import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { CreateCardPage } from "./admin/cards/CreateCardPage";
import { CreateLocationPage } from "./admin/locations/CreateLocationPage";
import { MatchPage } from "./game/MatchPage";

/* Rutas de la aplicación. Cada pantalla nueva se agrega aquí. */
export function App() {
  return (
    <Routes>
      <Route path="/partida" element={<MatchPage />} />
      <Route element={<AdminLayout />}>
        <Route path="/admin/cartas/nueva" element={<CreateCardPage />} />
        <Route path="/admin/ubicaciones/nueva" element={<CreateLocationPage />} />
        <Route path="*" element={<Navigate to="/admin/cartas/nueva" replace />} />
      </Route>
    </Routes>
  );
}
