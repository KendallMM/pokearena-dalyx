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

Las reglas de recompensa se configuran en `.env`, sin valores ficticios:

- `INITIAL_CARD_CODES`: arreglo JSON de códigos únicos de cartas reales que
  defina el equipo de producto. Se entrega una copia de cada carta; todas deben
  estar en estado `available`.
- `INITIAL_CUBES`: cantidad entera no negativa; vacía significa sin configurar.
- `INITIAL_COLLECTION_RETRY_SECONDS`: intervalo entre intentos, 60 por defecto.

Si faltan reglas o cartas disponibles, el jugador entra y recibe el mensaje de
colección no disponible o pendiente. La solicitud se guarda junto con su cuenta;
el planificador existente la reintenta aunque no vuelva a iniciar sesión.
Cartas, cubos y confirmación se guardan en una sola transacción. Volver a entrar
o ejecutar dos entregas simultáneas no duplica la recompensa.
Después de cambiar las reglas del ambiente, reconstruye/recrea el backend.
Las reglas nuevas se aplican a entregas aún pendientes, nunca a las ya completadas.

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
