# Frontend de Poké-Arena

React, Vite y los componentes existentes integran el acceso real con Google.
El jugador entra en `/partida`; las cuentas con rol `content_admin` conservan
las pantallas de crear cartas, buscar cartas y crear ubicaciones.

## Ejecutar

Desde la raíz ejecuta `docker compose up --build` y abre http://localhost:5173.
Sigue la configuración de Google OAuth y recompensas del [README principal](../README.md).
No hace falta instalar Node en el equipo.

La ventana de Google vuelve a `/auth/google/callback`. El callback quita el token
del fragmento y lo entrega solamente a su ventana de origen. El cliente verifica
origen, ventana y `state`; el backend verifica firma y `nonce` de un solo uso.
Cerrar la ventana o rechazar el acceso muestra la cancelación sin enviar el POST
de inicio de sesión. Bloquear ventanas emergentes muestra cómo continuar.

El cliente HTTP usa `/api/...` y Vite reenvía al backend. Las peticiones posteriores
llevan el bearer de Poké-Arena. El token de Google no se conserva ni se usa como
autorización interna. El bearer propio vive solo en memoria y vence automáticamente.
Recargar la página requiere identificarse de nuevo.

## Estructura

| Carpeta | Responsabilidad |
| --- | --- |
| `src/ui/` | Componentes reutilizables independientes de la API. |
| `src/api/` | Cliente HTTP único y servicios por recurso, incluidas sesiones. |
| `src/session/` | Cuenta y credencial interna en memoria; vencimiento y cierre de sesión. |
| `src/auth/` | Inicio con Google, callback y protección de rutas por sesión. |
| `src/admin/` | Administración del catálogo y acceso visual por rol. El backend autoriza cada operación. |
| `src/game/` | Partida existente con datos de ejemplo y resultado de la colección inicial. |
| `src/test/` | Preparación y servicios simulados solo para pruebas. |

Los componentes y servicios nuevos se escriben en JavaScript/JSX según los
estándares del proyecto. Los límites de API y contextos ya existentes conservan
TypeScript para mantener compatibles las pantallas actuales. `allowJs` permite
integrar ambos sin agregar dependencias.

## Pruebas

Desde la raíz:

```bash
docker compose -p pokearena-tests -f docker-compose.test.yml run --build --rm --no-deps frontend-test
```

Ejecuta Vitest, TypeScript, Prettier y la compilación de Vite. La compilación
comprueba también los contratos de las pantallas existentes.

## Agregar una pantalla

1. Crea la funcionalidad en su carpeta correspondiente.
2. Centraliza sus peticiones en `src/api/`, agrégala a `ApiServices` y a
   `fakeServices` de `src/test/fixtures.ts`.
3. Agrega la ruta en `src/App.tsx` y, si es administrativa, su opción en
   `src/admin/menuOptions.ts`.
4. Reutiliza los componentes de `src/ui/` y agrega pruebas junto al código.

Las validaciones del navegador ayudan al usuario; la validación y autorización
definitivas viven en el servidor. Las creaciones del catálogo siguen usando
`useOperationKey` para evitar duplicados en los reintentos.
