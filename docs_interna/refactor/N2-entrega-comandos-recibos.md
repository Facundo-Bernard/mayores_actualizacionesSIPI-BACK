# N2 — Entrega: comandos idempotentes, recibos y cierre económico

Fecha: 5 de noviembre de 2026.
Estado: implementado y verificado contra MongoDB real en la base aislada `mayores_actualizaciones_test`.
Sin desplegar, sin migraciones y sin escrituras en la base compartida. Nada commiteado.

## 1. Alcance

Incluido:

- Frontera `ejecutar_comando` que confirma estado, recibo y obligación económica con una sola escritura (CAS de documento único).
- Recibo durable por comando con hash canónico, recuperación por clave y rechazo de reuse con otro contenido.
- Obligación económica embebida en el cierre, liquidación idempotente y reconciliador de pendientes.
- Lectura autorizada de recibo y snapshot.
- Bloqueo de mutaciones legacy sobre runs del protocolo v3.
- Intento narrativo con puntaje tomado del catálogo editable del panel (`puntos_por_calificacion`).

No incluido (etapas siguientes):

- Montaje de rutas `/api/narrative/v3` (N4).
- Proyección `SnapshotRunV3` y recibo de creación `INICIAR_PARTIDA` (N4/N5).
- Reconciliador periódico conectado al `lifespan` de `main.py` (requiere autorización, ver §9).

## 2. Decisiones D08 aplicadas

D08 estaba aprobada como «transacciones si el entorno las soporta; si no, documento único con CAS». La medición dio standalone, por lo que se aplicó la rama de documento único.

- **Almacenamiento:** recibos y obligación viven dentro de `narrative_runs`, sin colección auxiliar y sin transacciones.
- **Semántica:** hash canónico de `{type, payload, expectedVersion}` (más `date` en creación); alcance de clave por run; búsqueda de recibo antes de validar versión; RNG inyectado por el llamador y resultado persistido en el recibo.
- **Retención:** el recibo conserva el estado confirmado completo (sin `recibos` ni `liquidacion` anidados) mientras viva la run o su archivo. No se poda; el crecimiento se acota con el límite de 2 MB descrito en §7.

## 3. Evidencia del entorno (base aislada)

- `setName = None` → standalone, sin transacciones multi-documento.
- `isWritablePrimary = true`, write concern por defecto (acknowledged).
- `maxBsonObjectSize = 16.777.216`, `maxWriteBatchSize = 100.000`.

Índices relevantes verificados:

- `narrative_runs`: único `(user_id, date, game_id)` y `(user_id, date desc)`.
- `narrative_runs_archive`: solo `_id`.
- `user_attempts`: único `(user_id, game_id, date)`.
- `economy_ledger`: único `idempotency_key` y `(status, created_at)`.

Índice ensayado (creado **solo** en la base de pruebas): parcial `liquidacion_pendiente` sobre `narrative_runs` con `liquidacion.estado` y `liquidacion.creada_en`, filtro `liquidacion.estado = "pendiente"`. `explain` con `hint` confirma `IXSCAN`. Su creación en la base compartida queda pendiente de autorización.

## 4. Esquema persistido

Campos agregados a `narrative_runs` (y por copia a `narrative_runs_archive`):

| Campo | Contenido |
|---|---|
| `protocolo` | `"v3"`. Las rutas legacy responden 409 si intentan mutar una run con esta marca. |
| `version` / `generation` | OCC existente; el CAS exige ambos. |
| `recibos[]` | `commandId`, `type`, `commandHash`, `previousVersion`, `version`, `generation`, `estado`, `consecuencias`, `resultado`, `recompensa`, `created_at`. |
| `liquidacion` | `rewardId`, `estado` (`pendiente`/`liquidada`/`local`), `puntos`, `canal` (`ledger`/`local`), `grade`, `rango`, `creada_en`, `liquidada_en`. |

`estado` del recibo es la proyección de dominio sin `_id`, `recibos` ni `liquidacion`, para que el recibo no crezca recursivamente.

## 5. Orden de validación

1. Cargar run activa (404 `run_not_found`) y verificar propietario (`403`).
2. Verificar `protocolo == "v3"` (`phase_conflict`) y `generation` (`generation_conflict`).
3. Calcular hash canónico y buscar el recibo **antes** de mirar `expectedVersion`.
   - Existe y el hash coincide → se recupera sin reevaluar reglas ni RNG.
   - Existe y el hash difiere → `command_reused` sin mutación.
4. Verificar `expectedVersion == version` (`version_conflict` con `currentVersion`).
5. Rechazar comandos sobre runs `completed`/`game_over` (`phase_conflict`).
6. Resolver sobre copia profunda; un fallo del resolver no muta nada.
7. CAS `{_id, protocolo, generation, version}` con `$set` + `$push` del recibo y, si hay cierre, `liquidacion`.
8. Perdedor del CAS → recibo del ganador si existe; si no, `version_conflict`.
9. Ganador → liquidación; si falla, la obligación queda `pendiente` y la respuesta informa ese estado.

Commit incierto: un error de red posterior a la escritura se traduce en `command_outcome_unknown` (503, `retryable`). El reintento con la misma clave recupera el recibo confirmado.

## 6. Contrato de recompensa

- `rewardId = reward:narrativo:<principal.key>:<date>`, con `principal.key` derivado de la credencial (`user_<id>` o `guest_<guest_id>`), nunca de un campo del cliente.
- Cuentas: canal `ledger`, `liquidacion.estado` (`pendiente` → `liquidada`). La acreditación usa la clave `(user_id, attempt, narrativo, date, normal)` y `ledger_applied` evita el doble `$inc` si el crédito se aplicó antes de una caída.
- Invitados: canal `local`, `liquidacion.estado = local`; auditoría única en `economy_ledger` (`guest_narrative`) y sin saldo del lado servidor. La derrota de invitado no genera auditoría.
- El intento (`user_attempts`) se registra con `score` y `stars` tomados del catálogo que edita el panel: `score = puntos_por_calificacion[grade]`, estrellas fijas por rango (S=3, A=3, B=2, C=1, F=0, igual que el panel). Una derrota guarda `score = 0`, `stars = 0`. En el camino de obligación se usa el snapshot de puntos tomado al confirmar, para que el intento y el crédito coincidan aunque el admin cambie la configuración entre confirmación y reconciliación.
- El primer intento completado del día no se degrada: un reinicio posterior (derrota de otra generación) no pisa `completed` ni vuelve a acreditar.

## 7. Tamaño y retención

Runs reales de la base de pruebas: 4.759, 6.055 y 6.210 bytes (la mayor, mes 12 / versión 40). Simulación con estado completo por recibo:

| Recibos | Documento |
|---|---|
| 12 | 87.637 B |
| 24 | 169.045 B |
| 48 | 331.861 B |
| 96 | 657.493 B |
| 192 | 1.308.849 B |

Se fija un tope de 2 MB para runs nuevas. Una run que lo superara no se confirma: el límite se valida antes de publicar el recibo, de modo que nunca queda estado sin recibo ni recibo sin estado.

## 8. Reconciliación

`reconciliar_liquidaciones_pendientes(older_than_seconds=60)` busca `liquidacion.estado = "pendiente"` con `creada_en` anterior al corte y aplica `aplicar_liquidacion` por run. Cubre:

- cierre confirmado sin intento/asiento;
- crédito aplicado seguido de caída antes de marcar `liquidada` (la clave y `ledger_applied` evitan el doble crédito);
- errores por run aislados con log, sin abortar el barrido.

## 9. Pruebas

- `tests/contract/test_narrative_n2_commands.py`: 17 pruebas — confirmación/recuperación, reuse con payload distinto, versión vieja, 6 comandos simultáneos, dos `commandId` simultáneos, propiedad y generación, fallo del resolver, commit incierto, cierre con obligación, reparación sin doble crédito, derrota, invitado, bloqueo legacy, lectura autorizada, hash canónico y tope de tamaño.
- `tests/contract/test_narrative_economy.py`: 8 pruebas, incluida la que fija que el intento narrativo usa `puntos_por_calificacion` editable.
- Suite por defecto: **263 passed, 18 deselected**. Integración (Mongo real): **13 passed**.

## 10. Limitaciones y autorizaciones pendientes

1. Crear el índice parcial `liquidacion_pendiente` en la base compartida requiere autorización específica (solo está probado en la base aislada).
2. Conectar `reconciliar_liquidaciones_pendientes` al ciclo periódico de `main.py` requiere autorización, porque opera sobre la base que use el proceso.
3. Montar y publicar `/api/narrative/v3` es N4; no se expone ninguna ruta nueva en esta etapa.
4. `SnapshotRunV3` devuelve hoy `{runId, generation, version, estado}`; la proyección completa y el recibo de `INICIAR_PARTIDA` son N4/N5.
5. Reinicio legacy: `expected_version` es opcional para no romper al cliente actual. Un reintento tardío de `/reiniciar` después de crear una generación nueva archiva esa generación. El arreglo definitivo requiere que el cliente envíe `expected_version` (o un token equivalente); el servidor ya lo respeta cuando viene.
6. Riesgos heredados de la revisión de N1, sin cambios en N2: copia de archivo potencialmente obsoleta si falla el delete del CAS; credencial de invitado firmada con el mismo secreto que los JWT de usuario; `X-Forwarded-For` falsificable en el límite de credenciales; `/reiniciar` sin `response_model`.

## 11. Traspaso

- **N3:** las referencias de contenido (revisiones) aún no viajan en el recibo; el punto de enganche es el resultado persistido del comando.
- **N4:** consume `ejecutar_comando` y la lectura autorizada tal como están; falta el montaje de rutas, la proyección de snapshot y el recibo de creación.
