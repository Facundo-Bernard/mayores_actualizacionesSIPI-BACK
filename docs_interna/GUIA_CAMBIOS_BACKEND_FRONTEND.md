# Cambios de backend para el frontend

> **Estado:** 4/11/2026 · rama `feature/refactor-backend`.
> **Alcance:** contrato que consume la SPA de juegos (Ionic) y el juego narrativo. El panel administrativo queda fuera de esta guía.
> **Premisa:** el contrato se mantuvo. No hay rutas, métodos, campos obligatorios ni códigos del camino feliz eliminados o renombrados. Lo nuevo es aditivo y el frontend puede seguir funcionando sin cambios; las acciones marcadas como **requeridas** son para corregir bugs o aprovechar datos que hoy se pierden.

---

## 0. Resumen

| Tema | Problema que resuelve | Qué cambió en el contrato | Acción del frontend | Estado |
|---|---|---|---|---|
| Identidad en intentos | Se podía guardar progreso a nombre de otro usuario | `POST/GET /api/games/attempts*` exigen Bearer; `user_id` del body/query se ignora | Ninguna: el frontend ya no llama sin cuenta | Activo |
| Acreditación única | Replay y doble POST acreditaban dos veces | Mismo endpoint; un replay responde `puntos_ganados: 0` | Manejar `0` y el documento vigente | Activo |
| Saldo autoritativo | El saldo mostrado podía diferir de la DB | `puntos_ganados` y `puntos_totales_usuario` en la respuesta | Leer y mostrar el saldo del servidor | Activo |
| Dificultad separada | Fácil y difícil de Crucigrama compartían intento | Se guarda por dificultad; la API todavía no lo expone | Ninguna por ahora (pendiente backend) | Parcial |
| Pistas | Cobraba sin contenido y podía cobrar dos veces | Misma forma de request/response; no cobra sin pista ni al repetir | Manejar `pista: null` y `message` | Activo |
| Recarga de vidas | La recarga de las 4 vidas daba 403 | Nueva ruta `POST /api/economy/refill-lives` | Reemplazar la llamada al endpoint admin | Activo |
| Puntos de invitado | El invitado no veía los puntos del narrativo | Nueva ruta `POST /api/economy/guest-migration` | Llamarla una vez al crear la cuenta | Activo |
| Puntos narrativos | El invitado no recibía puntos; la cuenta no los veía | `puntos_ganados` en las respuestas del ciclo V2 | Sumar en local solo si es invitado | Activo |
| Aislamiento de invitado | Todos los invitados compartían `run_0_<fecha>` | Header opcional `X-Guest-Id` | Enviar un id persistente por dispositivo | Activo |
| Motor narrativo | V1 es el operativo; V2 es el objetivo | El motor se elige por universo y se informa en `motor` | Hoy operar V1; dejar la UI lista para V2 | Actual/futuro |
| Discriminador de motor | El frontend debía inferir V1/V2 | Campo `motor` en `iniciar`, `elegir-carta-mes` y `estado` | Opcional, para enrutar la UI | Activo |
| Endpoints planos | Rutas V1 convivían con V2 sin señal | Marcados `deprecated`; siguen funcionando | Migrar por universo; no usarlos en V2 | Activo |
| Conflictos | Fases inválidas y escrituras concurrentes | `409` con `detail` descriptivo | Recargar estado antes de reintentar | Activo |
| Límite de tasa | Farming y doble click | `429` + `Retry-After` en economía, intentos y narrativo | Backoff y reintento | Activo |
| Desafío sanitizado y feedback | La solución viaja al cliente | Aún no implementado | Ninguna | Pendiente |
| Generación y RAE | Ráfagas de consultas y 429 internos | Sin cambios de contrato | Ninguna | Interno |

---

## 1. Lo que se mantuvo

- Las rutas y métodos existentes de desafíos, intentos, economía y narrativo.
- Los campos actuales de request y response; solo se agregaron campos opcionales.
- Los códigos de respuesta del camino feliz y de los errores ya documentados.
- El modo invitado de los clásicos: `GET /api/challenges/today` y `GET /api/challenges/date/{date}` siguen públicos y sin autenticación.
- El contrato de desafíos: `config`, `solution`, `cells`, `words`, `grid`, `boards` siguen disponibles. La sanitización es un trabajo posterior y no se activó.
- Los endpoints planos del narrativo siguen respondiendo para universos V1.

Los cambios de comportamiento que sí pueden observarse son: `401` en intentos sin token, `409` en narrativo ante fase o versión inválida, `429` por límite de tasa y `puntos_ganados: 0` en replays. Ninguno altera el camino feliz de un jugador con sesión.

---

## 2. Clásicos y economía

### 2.1 Identidad en intentos

`POST /api/games/attempts`, `GET /api/games/attempts/date/{date}` y `GET /api/games/attempts` ahora toman el usuario del token. El `user_id` enviado en el body o en el query se ignora.

- Sin token: `401` con `detail: "Autenticación requerida. Token no proporcionado."`
- Con token: se escribe y se lee únicamente el progreso de ese usuario.
- El modo invitado no se ve afectado porque el frontend ya guarda el progreso local y no llama a estos endpoints sin cuenta.

No requiere cambios si el frontend mantiene el Bearer y omite llamadas sin sesión.

### 2.2 Una acreditación por dificultad

La clave de acreditación es `(usuario, juego, fecha, dificultad)`. La dificultad se deriva de `difficulty` o de `game_data.difficulty`; si no viene, es `standard`.

- Si esa dificultad ya está completada, un POST posterior no cambia el estado, no recalcula grado y no vuelve a acreditar.
- La respuesta es `200` con el documento vigente y `puntos_ganados: 0`.
- Crucigrama fácil y difícil son slots independientes: completar uno no bloquea el otro.

Un `409` solo aparece ante una carrera de escritura excepcional: `"No se pudo guardar la partida por un conflicto concurrente."` Si ocurre, conviene recargar el intento antes de reintentar.

### 2.3 Saldo autoritativo

La respuesta de `POST /api/games/attempts` incluye:

- `puntos_ganados`: puntos acreditados **en esa request**. En un replay o en un intento no completado es `0`.
- `puntos_totales_usuario`: saldo actual del usuario luego de la operación.

Recomendación: mostrar `puntos_totales_usuario` en vez de sumar `score` localmente. Si se sigue sumando `score`, la UI puede divergir del saldo real.

Con los flags de validación server-side apagados (estado actual por defecto), el grado y el score se calculan igual que antes a partir de los campos del cliente. Cuando un juego tenga su flag `GRADING_ENFORCE_*` activo, el servidor recalcula grado/score/estrellas desde la submission; una submission inválida se persiste como `F` con `0` puntos y HTTP `200`, y no acredita.

### 2.4 Dificultad expuesta: pendiente

El backend guarda `by_difficulty` y la dificultad de cada slot, pero **la respuesta actual de intentos no incluye `difficulty` ni `by_difficulty`**. Por eso el calendario todavía no puede distinguir fácil de difícil desde la API. Es una deuda del backend; no hay acción posible del frontend hasta que se exponga.

### 2.5 Pistas

`POST /api/economy/use-hint` conserva request y response. Cambios de comportamiento:

- `difficulty` es opcional; si falta, el servidor la infiere del intento del usuario para esa fecha.
- Si no hay contenido para la pista, responde `success: true`, `puntos_descontados: 0`, `pista: null` y un `message` explicativo. No cobra.
- Si la misma pista ya se pidió, devuelve la misma información con `puntos_descontados: 0` y `message: "Esta pista ya fue desbloqueada; no se descontaron puntos."`.
- Si no alcanza el saldo: `400` con el detalle de puntos faltantes.

El frontend solo necesita aceptar `pista: null` sin tratar la respuesta como error.

### 2.6 Recarga de vidas (requerida para corregir el 403)

Hoy la recarga de las 4 vidas de partida llama a `POST /api/admin/economy/user/adjust`, que exige admin y devuelve `403` a un jugador. La ruta correcta es:

```http
POST /api/economy/refill-lives
Authorization: Bearer <token>
```

No lleva body. El servidor fija el precio en **50 puntos** y no acepta cantidad, costo ni vidas del cliente.

```json
{
  "success": true,
  "puntos": 270,
  "message": "Vidas recargadas por 50 puntos."
}
```

- Sin saldo: `400` con `"Puntos insuficientes. Necesitás 50 pts y tenés 10 pts."`
- Usuario inexistente: `404`.

Como las vidas de partida son locales, la respuesta no devuelve un contador de vidas: al recibir `success: true`, el cliente reinicia sus 4 vidas.

### 2.7 Migración de puntos de invitado (requerida al crear cuenta)

```http
POST /api/economy/guest-migration
Authorization: Bearer <token>
Content-Type: application/json

{ "guest_id": "g_7f3a9c", "puntos": 480 }
```

```json
{
  "success": true,
  "ya_migrado": false,
  "puntos_solicitados": 480,
  "puntos_migrados": 480,
  "tope": 1000,
  "puntos_totales": 480,
  "message": "Se migraron 480 puntos de invitado."
}
```

- Es **una sola vez por cuenta**. Una segunda llamada devuelve `success: false`, `ya_migrado: true`, `puntos_migrados: 0` y el saldo actual.
- El servidor aplica el tope `guest_migration_max_points` (1000 por defecto) y audita `solicitado`, `aplicado` y `tope`.
- Si no hay puntos: `success: false`, `ya_migrado: false`, `puntos_migrados: 0`.
- `guest_id` debe ser el mismo identificador que se usa en `X-Guest-Id` para el narrativo y cumplir `[A-Za-z0-9_-]{1,64}`.

Flujo sugerido: al crear la cuenta, llamar una vez, reemplazar el saldo local por `puntos_totales` y borrar el saldo de invitado de `localStorage`. Al iniciar sesión con otra cuenta, el saldo del servidor pisa el local.

### 2.8 Compras y desbloqueos

- `POST /api/economy/buy-lives` conserva la vía por `package_id`; el servidor define vidas y costo. La vía directa `{ "vidas": N }` ya no se usa: sin `package_id` se compra 1 vida al precio base, y se aplica `vidas_maximas`.
- `POST /api/economy/unlock-day` conserva request y response.
- `GET /api/economy/config` y `GET /api/economy/me` conservan su forma. Se agregó `guest_migration_max_points` a la configuración y `/me` ahora expone la racha real (§2.10).

### 2.9 Límite de tasa

Hay una ventana deslizante en memoria por identidad (token o IP):

| Prefijo | Límite |
|---|---|
| `/api/economy` | 120 req/min |
| `/api/games/attempts` | 120 req/min |
| `/api/narrative` | 180 req/min |

Al excederlo: `429` con header `Retry-After` (segundos) y body `{ "success": false, "detail": "Demasiadas solicitudes. Esperá unos segundos y reintentá." }`. En respuestas exitosas se agrega `X-RateLimit-Limit`. El frontend debería esperar el valor de `Retry-After` antes de reintentar.

### 2.10 Racha diaria

La racha no se envía desde el cliente ni se guarda como contador: el backend la deriva de `user_attempts`.

- Un día cuenta si tiene al menos un intento `mode: "daily"`, `status: "completed"` y no rechazado por validación. Varios juegos el mismo día suman un solo día.
- El día se decide en zona ART. Si el último día jugado es hoy, `racha_hoy_jugada` es `true`; si es ayer, la racha sigue viva; si es anterior a ayer, `racha` vale `0`.
- No hay endpoint nuevo ni campos nuevos en el request de intentos: se sigue usando `POST /api/games/attempts` y el `user_id` sale del Bearer. El cliente no puede inflar la racha.

`GET /api/economy/me` agrega:

```json
{
  "racha": 4,
  "racha_ultima_fecha": "2026-11-03",
  "racha_hoy_jugada": false
}
```

- Acción en el frontend: `recargarEconomia` hoy copia vidas, puntos, suscripción y días desbloqueados al snapshot `usuario`; agregar `racha` y `racha_hoy_jugada` al slice y a ese snapshot para que el header muestre el valor real. El invitado sigue con su valor local: no hay racha en servidor.
- Esta racha es la base para acreditar puntos por hitos en el futuro; ese día la acreditación se hará con el ledger existente y tampoco requerirá cambios en el request.
- Detalle de integración y checklist del header: [GUIA_RACHA_FRONTEND.md](GUIA_RACHA_FRONTEND.md).

---

## 3. Narrativo

### 3.1 Estado actual y objetivo: V1 hoy, V2 de grafos a futuro

Hay dos motores narrativos y el backend elige cuál usa cada universo.

- **Plan actual:** el motor **V1 plano** es el operativo. Resuelve el evento del mes en una sola decisión: el backend sortea un desenlace ponderado y devuelve el resultado.
- **Objetivo a futuro:** migrar los universos al motor **V2 de grafos**. V2 ya está implementado y probado, pero **todavía no es el oficial**: se activa por universo y su adopción depende del contenido/readiness y de que el frontend complete la migración. V1 se mantiene mientras tanto para no romper partidas y permitir rollback.

La URL es la misma en ambos motores. Lo que cambia es el cuerpo de la respuesta y qué endpoint resuelve la decisión. El frontend puede ramificar por `motor` o por la presencia de `grafo_actual`.

| Aspecto | V1 plano (actual) | V2 de grafos (objetivo) |
|---|---|---|
| Motor en la partida | `motor: "v1"` | `motor: "v2"` |
| Qué devuelve `elegir-carta-mes` | `evento_actual` con `opciones[]` | `grafo_actual` con `nodo_actual` |
| Información de las opciones | `id`, `texto`, `es_secreta`, `bloqueada`, `probabilidades[]` | `id`, `texto`, `disponible`, `motivo_bloqueo` |
| Desenlaces y porcentajes | Expuestos (`probabilidades[].porcentaje`) | Ocultos (anti-spoiler): no viajan al cliente |
| Cómo se decide | `POST .../decidir-evento` con `opcion_id`; el backend sortea el desenlace | `POST .../avanzar-nodo` con `opcion_id`, repetido mientras el grafo no termine |
| Cómo llega el resultado | `resultado_actual` con los efectos ya aplicados | El nodo siguiente trae `resultado_texto` e `impactos_*`; no hay `resultado_actual` |
| Conversación incidental | 40% tras el evento; se resuelve con `responder-conversacion` | 40% tras el evento; la conversación también es un grafo y se resuelve con `avanzar-nodo` |
| Evento especial por afinidad | No existe | Se encadena solo al cerrar un evento si se cruza el umbral (lealtad ≥ 95 o traición < 15); puede ocurrir más de una vez |
| Significado de `es_final` | No aplica | `true` = fin de **ese grafo**, no fin de la partida; después se vuelve a `BALANCE_MES` |
| Fin de partida | `FINALIZADA` al mes 12 o por colapso de recursos | Igual: `FINALIZADA` al mes 12 con `avanzar-mes`; el colapso puede devolver `status`/`finalizacion` desde el grafo |
| Estado y recarga | `GET .../estado` devuelve los punteros planos | `GET .../estado` devuelve `grafo_actual` y el nodo actual |
| Rutas planas | Son el camino normal | `409` en los POST planos; los GET planos devuelven `null` o vacío |

Flujo V1:

```text
DRAFT_MENSUAL
  └─ POST elegir-carta-mes      → evento_actual { opciones[].probabilidades[] }
       └─ POST decidir-evento   → resultado_actual
            ├─ 40%  → RESOLVER_CONVERSACION → POST responder-conversacion
            └─ resto → BALANCE_MES
  └─ POST avanzar-mes           → mes siguiente / FINALIZADA (mes 12)
```

Flujo V2:

```text
DRAFT_MENSUAL
  └─ POST elegir-carta-mes      → grafo_actual { nodo_actual, opciones[] }
       └─ POST avanzar-nodo     → nodo siguiente (repetir mientras es_final = false)
            ├─ nodo terminal → aplica impactos
            │    ├─ evento especial de afinidad → nuevo grafo (seguir con avanzar-nodo)
            │    ├─ 40% conversación           → grafo de conversación (avanzar-nodo)
            │    └─ resto                      → BALANCE_MES
            └─ colapso de recursos → finalizacion / status terminal
  └─ POST avanzar-mes           → mes siguiente / FINALIZADA (mes 12)
```

Reglas de renderizado:

- **No inventar porcentajes en V2.** Si la UI muestra chances, solo puede hacerlo con `probabilidades` de V1. En V2 no existen.
- **En V2 no hay `resultado_actual`.** El desenlace se lee del nodo que llega (`resultado_texto`, `impactos_recursos`, `impactos_afinidad`, `impactos_tags`).
- **En V2 usar `disponible` y `motivo_bloqueo`** para habilitar opciones y explicar bloqueos. Las opciones marcadas como ocultas no se envían.
- **`es_final` no es game over.** Mostrar el cierre del grafo y continuar con el balance; la partida termina por mes 12 o por colapso.
- **`afinidad` y `recursos`** en la respuesta de V2 solo vienen con datos cuando el nodo es final; en nodos intermedios pueden ser `null`.
- **Una conversación V2 no es un evento.** Llega con `tipo: "conversacion"` y se resuelve con el mismo `avanzar-nodo`.

Reglas de migración:

- Mientras el universo siga en V1, no hay nada que cambiar: el ciclo plano sigue siendo válido.
- Pasar un universo a V2 es una decisión de backend por universo; la URL no cambia.
- Con `motor: "v2"`, no llamar a los POST planos (`decidir-evento`, `responder-conversacion`): responden `409`. Toda decisión va por `avanzar-nodo`.
- Con `motor: "v2"`, los GET planos de consulta (`evento-actual`, `conversacion-actual`, `resultado-actual`, `draft-actual`) devuelven `null` o vacío; el estado real se lee de `GET .../estado`.
- No asumir que un universo será siempre V1 ni que V2 ya está activo en todos: consultar `motor` al iniciar y al recargar.

El detalle técnico completo, con ejemplos de payload de cada motor, está en `app/features/narrative/docs/ANALISIS_DIFF_V1_V2.md`.

### 3.2 Contrato intacto

Las rutas del ciclo (`iniciar`, `elegir-carta-mes`, `decidir-evento`, `responder-conversacion`, `avanzar-mes`, `estado`, `avanzar-nodo`, `historial`, `corte`, `reiniciar`, etc.) no cambiaron. El motor se elige por universo; el frontend no necesita cambiar URLs para seguir jugando.

### 3.3 Identidad de invitado (header `X-Guest-Id`)

Los routers `/api/narrative/v2/partida/*` y `/api/narrative/partida/*` aceptan:

```http
X-Guest-Id: g_7f3a9c
```

- Formato: letras, números, guiones y guiones bajos, máximo 64 caracteres.
- Aísla la partida del invitado. Sin el header, todos los invitados siguen compartiendo `run_0_<fecha>` y no se acreditan puntos.
- Es opcional para no romper el comportamiento actual, pero **recomendado** para cualquier flujo de invitado.
- Debe ser estable por dispositivo (persistirlo en `localStorage`).

### 3.4 Puntos del narrativo

`puntos_ganados` se agregó como campo opcional en:

- `POST /api/narrative/v2/partida/iniciar`
- `POST /api/narrative/v2/partida/elegir-carta-mes`
- `POST /api/narrative/v2/partida/decidir-evento` (ruta V1, deprecada)
- `POST /api/narrative/v2/partida/avanzar-mes`
- `POST /api/narrative/v2/partida/avanzar-nodo`, cuando el nodo es terminal (`EstadoGrafoV2Response`)

Puede venir `null` cuando la partida no terminó. Cuando trae un número, son los puntos acreditados en esa request.

Regla de consumo:

- **Cuenta autenticada:** el servidor ya acreditó los puntos. El frontend **no** debe sumarlos localmente; solo mostrarlos o refrescar el saldo.
- **Invitado con `X-Guest-Id`:** el servidor no escribe saldo; devuelve los puntos para que el frontend los sume en `localStorage`. La acreditación es idempotente por `(guest_id, narrativo, fecha)`, así que un reintento devuelve `0` y no duplica.
- **Invitado sin `X-Guest-Id`:** no se acreditan puntos.

`reiniciar` no vuelve a acreditar la misma partida/fecha.

### 3.5 Discriminador `motor`

Se agregó `motor: "v1" | "v2"` en las respuestas de:

- `POST /api/narrative/v2/partida/iniciar` (ya existía)
- `POST /api/narrative/v2/partida/elegir-carta-mes`
- `GET /api/narrative/v2/partida/estado`

Es aditivo. Sirve para enrutar la UI sin inferir el motor por la presencia de `grafo_actual`, pero no es obligatorio.

### 3.6 Endpoints planos `deprecated`

Siguen funcionando para universos V1, pero están marcados como deprecados:

- `POST /api/narrative/v2/partida/decidir-evento`
- `POST /api/narrative/v2/partida/responder-conversacion`
- `GET /api/narrative/partida/evento-actual`
- `GET /api/narrative/partida/conversacion-actual`
- `GET /api/narrative/partida/resultado-actual`
- `GET /api/narrative/partida/draft-actual`

En una partida V2, los dos POST planos responden `409`; el camino correcto es `avanzar-nodo`. Los GET de consulta siguen respondiendo, pero devuelven `null` o vacío porque la partida V2 no usa esos punteros. No se eliminan hasta que el frontend migre por universo. El frontend ya usa `avanzar-nodo` cuando hay `grafo_actual`, así que no requiere cambios si mantiene esa bifurcación.

### 3.7 Conflictos `409`

Además del error de versión, las guardas de fase devuelven `409` cuando se intenta una acción que no corresponde al motor, la fase o el grafo activo (por ejemplo, avanzar sin grafo, iniciar un evento en una partida finalizada o mezclar V1/V2).

El conflicto de concurrencia usa este detalle:

```json
{
  "detail": "La partida fue modificada por otra petición. Recargá el estado actual antes de continuar."
}
```

Acción recomendada: al recibir `409`, volver a pedir `GET /api/narrative/v2/partida/estado` y reintentar desde el estado vigente. No reintentar a ciegas.

---

## 4. Pendiente del backend

Nada de esto requiere acción del frontend todavía:

1. **Exponer dificultad e `by_difficulty` en intentos.** Necesario para que el calendario muestre fácil y difícil por separado.
2. **Desafío sanitizado.** Una ruta de jugador que omita `solution`, `cells[].letter`, `words[].word`, `boards` y `grid`. El contrato actual sigue exponiendo la solución.
3. **Feedback server-side por jugada.** `POST /api/games/validate` para colores de Wordle, conflictos de Sudoku, palabras encontradas y letras correctas.
4. **V2 oficial y migración por universo.** Hoy el motor operativo es V1 y V2 se activa por universo; la declaración oficial depende de contenido/readiness y de la migración del frontend. El objetivo es pasar cada universo a V2 de grafos y retirar V1 cuando no queden universos planos. Mientras tanto, ambos motores conviven detrás de las mismas URLs.
5. **Flags de validación.** `GRADING_ENFORCE_WORDLE`, `_SOPA`, `_SUDOKU` y `_CRUCIGRAMA` están apagados por defecto. Cuando se activen, el servidor manda sobre grado/score/estrellas.

---

## 5. Sin impacto o fuera de alcance

- **Panel administrativo:** excluido de esta guía.
- **Generación de desafíos y RAE:** se redujo la concurrencia, se agregó espaciado entre consultas, backoff y caché negativa. Es interno y no cambia el contrato de desafíos.
- **Ledger, reconciliación, seeds, índices y separación de servicios:** internos.
- **`validation_status` y `validation_reason`:** se persisten para auditoría, pero no se exponen en la respuesta.
- **Vidas globales `usuarios.vidas`:** siguen siendo informativas; las vidas de partida siguen siendo locales.

---

## 6. Checklist de integración

Requerido para corregir bugs actuales:

- [ ] Recarga de vidas: usar `POST /api/economy/refill-lives` sin body y reiniciar las 4 vidas locales al recibir `success: true`.
- [ ] Al crear cuenta: llamar una vez a `POST /api/economy/guest-migration` con el `guest_id` y el saldo local; reemplazar el saldo por `puntos_totales` y limpiar el local.
- [ ] Narrativo de invitado: enviar `X-Guest-Id` estable y sumar `puntos_ganados` en `localStorage`.
- [ ] Narrativo con cuenta: no sumar `puntos_ganados` localmente; el servidor ya acreditó.
- [ ] Intentos: mostrar `puntos_totales_usuario` en vez de sumar `score` local.
- [ ] Manejar `pista: null` y `puntos_descontados: 0` como respuesta válida.
- [ ] Manejar `429` respetando `Retry-After`.
- [ ] Racha: leer `racha` y `racha_hoy_jugada` de `/api/economy/me` y copiarlos al snapshot `usuario` (hoy el header usa un valor local).
- [ ] En `409` del narrativo, recargar `estado` antes de reintentar.

Opcional / cuando se migre por universo:

- [ ] Usar `motor` para enrutar la UI y leer `grafo_actual` en V2, `evento_actual` en V1.
- [ ] Resolver toda decisión V2 con `avanzar-nodo`; no llamar a `decidir-evento` ni `responder-conversacion` en V2.
- [ ] Tratar `es_final` como fin del grafo, no como fin de la partida, y encadenar el siguiente grafo o el balance.
- [ ] Consumir `by_difficulty` y el desafío sanitizado cuando el backend los exponga.

---

## 7. Ejemplos rápidos

Respuestas abreviadas: se muestran solo los campos relevantes para cada cambio.

Replay de un intento ya completado:

```http
POST /api/games/attempts
Authorization: Bearer <token>
Content-Type: application/json

{
  "game_id": "wordle",
  "date": "2026-11-04",
  "mode": "daily",
  "status": "completed",
  "word": "PERRO",
  "attempts": 3,
  "game_data": { "difficulty": "standard" }
}
```

```json
{
  "id": "...",
  "user_id": 42,
  "game_id": "wordle",
  "date": "2026-11-04",
  "mode": "daily",
  "status": "completed",
  "attempts": 3,
  "stars": 2,
  "score": 75,
  "grade": "B",
  "puntos_ganados": 0,
  "puntos_totales_usuario": 320
}
```

Puntos de invitado en el narrativo:

```http
POST /api/narrative/v2/partida/avanzar-mes
X-Guest-Id: g_7f3a9c
Content-Type: application/json

{ "date": "2026-11-04" }
```

```json
{
  "mes_actual": 12,
  "fase_actual": "FINALIZADA",
  "status": "completed",
  "recursos": { "dinero": 120, "influencia": 80, "poder": 60 },
  "finalizacion": { "rango": "B" },
  "puntos_ganados": 75
}
```

En este caso el frontend suma `75` al saldo de invitado en `localStorage`. Si la misma partida se reintenta, `puntos_ganados` vuelve a ser `0`.
