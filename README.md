# Poké-Arena

**Poké-Arena** es un juego de cartas Pokémon por turnos simultáneos, gratuito y para navegador. Una partida dura entre 6 y 8 minutos.

## Reglas y Mecánicas

- **Mazo:** Cada jugador arma un mazo de **12 cartas** con cartas de su colección. Cada carta tiene *costo*, *poder*, *tipo*, *rareza* y, opcionalmente, una *habilidad*.
- **Tablero y Turnos:** La partida se juega en **3 ubicaciones** durante **6 turnos**. En el turno *n*, cada jugador dispone de *n* puntos de energía para jugar cartas.
- **Resolución de Turnos:** En cada turno, ambos jugadores eligen sus jugadas en secreto. El turno se resuelve cuando los dos confirman o cuando vence el tiempo límite; en ese momento se revelan las cartas y se aplican sus efectos.
- **Poder:** La **ventaja de tipo** (por ejemplo, *Agua* sobre *Fuego*) y el efecto de cada ubicación modifican el poder de las cartas.
- **Victoria:** Gana el jugador con más poder en al menos **2 de las 3** ubicaciones.

## Clasificatorias y Recompensas

- **Apuestas:** En las partidas clasificatorias se apuestan **cubos** (la moneda del juego). 
  - **Dynamax:** Una vez por partida, cada jugador puede activarlo para *duplicar* la apuesta.
  - **Run:** Permite retirarse de la partida perdiendo solo la apuesta vigente.
- **Sistema de Nivel:** El nivel de cada jugador se mide con un **puntaje Elo**, que se usa para el emparejamiento y la clasificación general.
- **Fin de Partida:** El ganador se lleva los cubos apostados del perdedor, suma puntos en su Elo y el sistema le asigna una recompensa aleatoria que puede ser *cubos adicionales* o *cartas*.

## Desarrollo local con Docker

Necesitas Docker Engine y Docker Compose. Node.js, Python, MySQL, MongoDB y Redis
se ejecutan en los contenedores.

Si aún no tienes `.env`, créalo con `cp .env.example .env`. Cambia las contraseñas
de MySQL y usa un `JWT_SECRET` aleatorio de al menos 32 caracteres. Después:

```bash
docker compose up --build
```

- Aplicación: http://localhost:5173
- OpenAPI: http://localhost:8000/docs
- Estado de la API: http://localhost:8000/health

El frontend recarga al guardar. Para aplicar cambios del backend:
`docker compose up -d --build backend`. Las migraciones se aplican al arrancar.

## Inicio de sesión con Google

En Google Cloud configura la pantalla de consentimiento y crea un cliente OAuth
de tipo **Aplicación web**. Si está en pruebas, agrega las cuentas autorizadas.
Para desarrollo registra:

- Origen JavaScript: `http://localhost:5173`.
- URI de redirección: `http://localhost:5173/auth/google/callback`.

En `.env` configura `GOOGLE_CLIENT_ID` y `PUBLIC_APP_URL=http://localhost:5173`.
El flujo solicita un ID token mediante OIDC en una ventana emergente; no requiere
client secret. En producción registra el origen y la redirección HTTPS reales,
configura `PUBLIC_APP_URL` y usa `ENVIRONMENT=production`.

El navegador prepara un desafío de un solo uso, obtiene la identidad de Google
y envía `POST /api/v1/sesiones/google`. Vite quita `/api`; el endpoint del backend
es `POST /v1/sesiones/google`. Google se verifica criptográficamente; las APIs
posteriores usan exclusivamente el JWT de Poké-Arena.

`JWT_EXPIRATION_MINUTES` vale 15 por defecto y admite entre 1 y 60 minutos. El
bearer se guarda solo en memoria: al recargar, cerrar sesión o vencer la credencial
debes volver a identificarte. No hay contraseña local ni renovación automática.
El gateway conserva el contrato `code`, `message`, `field`, `correlation_id` en
los errores 401 y 503. `/v1/jugadores/yo` permite consultar la cuenta autenticada.

Las cuentas nuevas reciben rol `player` y Elo 0. La interfaz administrativa sigue
reservada a `content_admin`; el inicio de sesión nunca concede ese rol. Para
administración local, un operador debe asignar explícitamente ese rol a la cuenta
correspondiente en MySQL y luego volver a iniciar sesión.

### Colección y cubos iniciales

En su primer ingreso cada jugador recibe **15 cartas distintas de rareza Común**,
elegidas al azar en el servidor entre las cartas disponibles del catálogo, y
**1,000 cubos**. Son reglas del juego, no configuración.

- Cartas, cubos, el movimiento de +1,000 en el historial de cubos
  (`cube_movements`) y el recibo de la entrega se guardan en una sola
  transacción: se entrega todo o nada.
- Si el catálogo tiene menos de 15 cartas Comunes disponibles, la cuenta se crea
  sin cartas ni cubos y el jugador ve que el juego aún no está disponible. La
  entrega se completa en un ingreso posterior, cuando haya cartas suficientes.
- Cada ingreso vuelve a intentar una entrega pendiente. Además, el planificador
  la reintenta cada `INITIAL_COLLECTION_RETRY_SECONDS` (60 por defecto) aunque el
  jugador no vuelva a entrar.
- Volver a entrar o dos primeros ingresos simultáneos no duplican la recompensa.

### Pruebas aisladas, incluidas las de MySQL

```bash
docker compose -p pokearena-tests -f docker-compose.test.yml run --build --rm backend-test
docker compose -p pokearena-tests -f docker-compose.test.yml run --build --rm --no-deps frontend-test
docker compose -p pokearena-tests -f docker-compose.test.yml down
```

MySQL de pruebas utiliza almacenamiento temporal y credenciales exclusivas para
pruebas. Este entorno no monta los volúmenes de desarrollo. Sin `TEST_MYSQL_URL`,
Pytest omite expresamente las dos pruebas que requieren MySQL; las demás usan
la infraestructura existente con bases migradas de SQLite.

Las pruebas usan claves RSA generadas durante su ejecución y simulan solamente
el transporte de Google. Para comprobar el consentimiento real del proveedor hace
falta el cliente OAuth configurado y una cuenta autorizada.
