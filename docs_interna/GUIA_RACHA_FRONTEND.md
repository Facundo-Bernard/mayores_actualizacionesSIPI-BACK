# Racha diaria — contrato para el frontend

Estado: **backend listo, frontend todavía no la consume**. El valor existe en `GET /api/economy/me`, pero el header sigue mostrando el snapshot local de `usuario`.

---

## 1. Qué expone el backend

`GET /api/economy/me` (requiere Bearer) agrega tres campos al response existente:

```json
{
  "user_id": 42,
  "vidas": 5,
  "puntos": 1090,
  "racha": 4,
  "racha_ultima_fecha": "2026-11-03",
  "racha_hoy_jugada": false,
  "suscripcion": "basica",
  "dias_desbloqueados": [],
  "costo_pista_puntos": 20
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `racha` | `int` | Días consecutivos con al menos un desafío diario completado. `0` si no jugó hoy ni ayer. |
| `racha_ultima_fecha` | `string \| null` | Último día con un desafío diario completado (`YYYY-MM-DD`). Puede ser viejo incluso con `racha: 0`. `null` si nunca completó uno. |
| `racha_hoy_jugada` | `bool` | `true` solo si ya completó un desafío diario hoy (zona ART). |

El cálculo está en [app/shared/streak.py](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/shared/streak.py#L23) y se expone desde [lives.py](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/economy/lives.py#L53). El schema está en [schemas.py](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/economy/schemas.py#L119).

---

## 2. Semántica

- **Un día cuenta una sola vez**, aunque complete Wordle, Sudoku y Crucigrama el mismo día.
- Cuenta cualquier intento que el backend persista con `mode: "daily"`, `status: "completed"` y `validation_status != "rejected"`. El narrativo entra porque también guarda `mode: "daily"`.
- **No cuentan** intentos en curso, intentos de validación rechazada, modo `campaign`, ni fechas futuras.
- **Zona horaria**: el "hoy" es `America/Argentina/Buenos_Aires`, igual que los desafíos diarios.
- **Gracia de un día**: si jugó ayer pero todavía no hoy, la racha sigue viva y `racha_hoy_jugada` es `false` (el header puede mostrar la racha igual).
- Si el último día jugado es anterior a ayer, `racha` vuelve a `0`.
- La racha se calcula sobre la **fecha del desafío** enviada en el intento, no sobre el momento del envío. Completar un día atrasado desde "continuar desafío" cuenta para ese día.

---

## 3. Qué NO cambia

- No hay endpoint nuevo.
- El request de `POST /api/games/attempts` no cambia: el backend toma `user_id` del Bearer y `date` del intento. **El cliente nunca envía la racha** y no puede inflarla.
- La respuesta de `POST /api/games/attempts` **no** incluye la racha. Después de guardar, el front ya dispara `user_progress_updated` y recarga economía; de ahí sale el valor actualizado.
- Los invitados no tienen racha en servidor: siguen con el valor local.

---

## 4. Acciones en el frontend

Hoy `recargarEconomia` lee `/api/economy/me` pero descarta la racha, y el header lee un campo que nadie actualiza.

1. **Estado**: agregar `racha` (y opcionalmente `rachaHoyJugada`) a `PlayerEconomyState` en [playerEconomySlice.ts](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/store/playerEconomySlice.ts#L30), con default `0`.
2. **Dispatch**: en [PlayerEconomyContext.tsx:143](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/context/PlayerEconomyContext.tsx#L143), sumar `racha: userData.racha` y `rachaHoyJugada: userData.racha_hoy_jugada` al `actualizarEconomia`.
3. **Snapshot**: en [PlayerEconomyContext.tsx:148](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/context/PlayerEconomyContext.tsx#L148), copiar también `u.racha = userData.racha` (y `u.racha_hoy_jugada`) antes de reescribir `localStorage`.
4. **Header**: [LoginHeader.tsx:249](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/VISTAS/LOGIN/LoginHeader.tsx#L249) muestra `usuario.racha ?? 1`. Dos opciones:
   - dejar que lea del snapshot y actualizar el snapshot como en el paso 3, o
   - leer `racha` del contexto de economía, que es la fuente sincronizada.
5. **Cero**: el `?? 1` actual convierte `racha: 0` en `1`. Con el valor real, definir si se muestra `0` o se oculta el ícono de llama; no mostrar `1` cuando la racha está cortada.

### Flujo esperado

```
Partida completada → POST /api/games/attempts
                   → backend acredita y recalcula
                   → front dispara user_progress_updated
                   → GET /api/economy/me
                   → dispatch racha → header actualizado
```

---

## 5. Verificación rápida

```bash
curl -s http://localhost:8090/api/economy/me \
  -H "Authorization: Bearer <token>"
```

Casos para probar desde el front:

| Escenario | `racha` | `racha_hoy_jugada` | `racha_ultima_fecha` |
|---|---|---|---|
| Usuario nuevo, sin partidas | `0` | `false` | `null` |
| Completó hoy y los dos días previos | `3` | `true` | hoy |
| Completó ayer y anteayer, nada hoy | `2` | `false` | ayer |
| Último día jugado fue anteayer | `0` | `false` | anteayer |
| Completó dos juegos hoy | `1` | `true` | hoy |
| Completó un día atrás desde "continuar" | la racha de esa fecha | según hoy | la fecha del desafío |

---

## 6. Puntos por racha (futuro, sin trabajo en el front)

Cuando se habiliten puntos por hitos de racha, la acreditación se hará en el mismo `POST /api/games/attempts` con el ledger idempotente por `(usuario, "racha", fecha)`. El front no cambia: sigue leyendo `puntos` y `racha` de `/api/economy/me`.
