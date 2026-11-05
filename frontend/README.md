Frontend de Poké-Arena
======================

Interfaz web del administrador de contenido. Por ahora tiene las pantallas **Crear carta** y **Crear ubicación**.

Cómo correrlo
-------------

Todo se corre con Docker, no necesitas instalar Node.

1.  Desde la raíz del repositorio: `docker compose up --build`
2.  Abre http://localhost:5173
3.  Regístrate. Por ahora las cuentas se guardan solo en ese navegador, porque el backend aún no tiene registro ni inicio de sesión.
4.  Para crear cartas y ubicaciones, pega un token en la barra superior (ver abajo).

El frontend llama a `/api/...` y Vite lo reenvía al backend, así que no hay problemas de CORS.

Token de desarrollo
-------------------

La cuenta no da acceso a la API: eso lo da el token. Genéralo dentro del contenedor del backend:

```
docker compose exec backend python -c "import os,jwt,datetime as d;print(jwt.encode({'sub':'dev','role':'content_admin','iss':os.environ['JWT_ISSUER'],'aud':os.environ['JWT_AUDIENCE'],'exp':d.datetime.now(d.timezone.utc)+d.timedelta(hours=1)},os.environ['JWT_SECRET'],algorithm='HS256'))"
```

Pégalo en el panel de sesión. Se guarda solo en esa pestaña. Para probar el error 403, cambia `content_admin` por otro rol.

Pruebas y revisiones
--------------------

```
docker compose run --rm --no-deps frontend npm test
docker compose run --rm --no-deps frontend npm run typecheck
docker compose run --rm --no-deps frontend npm run format:check
docker compose run --rm --no-deps frontend npm run build
```

Estructura
----------

| Carpeta | Para qué sirve |
| --- | --- |
| `src/ui/` | Componentes reutilizables (campos, botones, alertas, `GameCard`, `ThemeToggle`). No conocen la API. |
| `src/api/` | Cliente HTTP único y un archivo por recurso (`cards.ts`, `references.ts`). Maneja el token, el ETag y el formato de error. |
| `src/session/` | Token de la sesión y cuentas guardadas en el navegador. |
| `src/auth/` | Pantalla de iniciar sesión y registrarse. |
| `src/admin/` | Pantallas del administrador, una carpeta por funcionalidad. |
| `src/game/` | Pantalla de partida (`/partida`). Por ahora solo el diseño, con datos de ejemplo. |
| `src/test/` | Preparación de las pruebas y datos falsos. |

Cómo agregar una pantalla
-------------------------

1.  Crea una carpeta en `src/admin/` (por ejemplo `locations/`) con la página y sus reglas.
2.  Crea el servicio en `src/api/` (por ejemplo `locations.ts`) usando el cliente HTTP, y agrégalo a `ApiServices` en `ApiContext.tsx`. Agrégalo también a `fakeServices` en `src/test/fixtures.ts`.
3.  Agrega la ruta en `src/App.tsx`.
4.  Agrega la opción en `src/admin/menuOptions.ts`: aparece en el menú principal y en el menú ☰.
5.  Reutiliza los componentes de `src/ui/` y `accessMessages.ts` para los errores 401 y 403.
6.  Escribe las pruebas junto al código (`*.test.ts` o `*.test.tsx`).

Convenciones
------------

*   TypeScript estricto y Prettier (`npm run format`).
*   Las pantallas no llaman a `fetch`: usan los servicios de `src/api/`.
*   Las validaciones del cliente son una ayuda temprana; la validación real está en el servidor.
*   Cada operación de creación usa una llave de idempotencia (`useOperationKey`) para que un reintento no duplique datos.
