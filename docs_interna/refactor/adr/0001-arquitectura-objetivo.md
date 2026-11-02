# ADR 0001 — Arquitectura objetivo y reglas de dependencia

- **Fecha:** 2/11/2026
- **Estado:** aceptado
- **Contexto:** el backend funciona, pero routers, servicios, Mongo y reglas de negocio están mezclados. La refactorización debe ser strangler: mover lógica sin cambiar el contrato HTTP.

## Decisión

Estructura por feature con tres capas y validadores puros:

```text
app/
  core/                 # config, db, auth, middleware
  shared/               # clock, errors, ledger, idempotencia
  features/
    <feature>/
      router.py         # HTTP: valida entrada y delega
      schemas.py        # Pydantic
      service.py        # casos de uso
      repository.py     # acceso a Mongo, solo donde aporte
      validation/       # funciones puras (submission, config) -> resultado
```

## Reglas de dependencia

1. **`router → service → repository`.** El router no toca Mongo ni calcula grados.
2. **Sin imports `feature → feature`.** Lo compartido va a `app/shared/` o a una interfaz explícita. Hay un test ratchet con las violaciones actuales en [tests/unit/architecture_baseline.txt](../../../tests/unit/architecture_baseline.txt): no se agregan nuevas y cada extracción quita la suya.
3. **Validadores puros.** `(submission, config) → resultado`, sin DB, testeables solos.
4. **Un solo reloj.** `app/shared/clock.py` decide "hoy" en `America/Argentina/Buenos_Aires`; el resto recibe la fecha. El código existente migra en Fase 4.
5. **Errores de dominio** en `app/shared/errors.py`; el router los traduce a HTTP. Los routers actuales siguen usando `HTTPException` hasta que se toquen.
6. **Extracción con red.** Cada movimiento deja los tests de contrato verdes y no cambia el snapshot OpenAPI.

## Criterio de extracción

- Solo se mueve un módulo que la fase en curso necesita.
- Si no hay un segundo consumidor ni un test que lo exija, no se crea abstracción.
- El contrato manda: campos y códigos nuevos son aditivos u opcionales.

## Mapa actual → destino

| Hoy | Destino | Fase |
|---|---|---|
| `user_attempts/service.py` (grado + persistencia + acreditación) | `service.py` + `validation/` + ledger en `shared/` | 1-2 |
| `economy/service.py` (config, vidas, pistas, unlock, admin) | `economy/points.py`, `lives.py`, `hints.py`, `admin.py` | 1 |
| `narrative/game/*` (V1 y V2 mezclados) | `narrative/motor_v1/`, `motor_v2/`, `validation/` | 3 |
| `daily_challenges/service.py` (generación + persistencia + serialización) | separar por juego y responsabilidad | 4 |

Este mapa se actualiza cuando una extracción se completa.
