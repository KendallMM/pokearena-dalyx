import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { CreateCardPage } from "./admin/cards/CreateCardPage";

/** Rutas de la aplicación. Cada pantalla nueva se agrega aquí. */
export function App() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/admin/cartas/nueva" element={<CreateCardPage />} />
        <Route path="*" element={<Navigate to="/admin/cartas/nueva" replace />} />
      </Route>
    </Routes>
  );
}
