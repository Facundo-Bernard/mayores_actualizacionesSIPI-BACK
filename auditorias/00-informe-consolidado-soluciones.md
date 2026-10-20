# 00 — Plan maestro de soluciones (consolidado)

**Proyecto:** Backend "Mayores Actualizaciones" (SIPI Back) — FastAPI + MongoDB
**Ruta:** `C:\Users\nmonti\Desktop\proyectos\backend\mayores_actualizacionesSIPI-BACK`
**Fecha:** 19/10/2026
**Estado:** DOCUMENTACIÓN DE PLANIFICACIÓN — nada de esto está implementado. No se modificó código, no se ejecutó la app ni pytest y no se tocó la base de datos. Cada plan fue elaborado por un subagente a partir de su informe de auditoría correspondiente.

---

## Índice de planes de solución

| # | Plan | Basado en | Alcance |
|---|------|-----------|---------|
| 01 | [Arquitectura y modularidad — soluciones](01-arquitectura-y-modularidad-soluciones.md) | Informe 01 | 21 bloques SOL (25 hallazgos), refactor no-breaking, F0–F6 |
| 02 | [Persistencia y flujo de datos — soluciones](02-persistencia-y-flujo-de-datos-soluciones.md) | Informe 02 | 18 soluciones S1–S18, 3 olas, migraciones y verificación |
| 03 | [Seguridad — soluciones](03-auditoria-de-seguridad-soluciones.md) | Informe 03 | Remediación CR/AL/ME con fases, acciones ops y tests |
| 04 | [Desacoplamiento microservicios — soluciones](04-desacoplamiento-microservicios-soluciones.md) | Informe 04 | 20 work packages, F0–F5, contrato tentativo de Auth |
| 05 | [Eficiencia y rendimiento — soluciones](05-eficiencia-y-rendimiento-soluciones.md) | Informe 05 | 19 soluciones (RAE, CPU, Mongo, cachés, escala), F0–F3 |
| 06 | [Testing y calidad — soluciones](06-testing-y-calidad-soluciones.md) | Informe 06 | Pirámide por riesgo, Fase 0 + 7, CI, lint y docs |

---

## 1. Estrategia general: 4 oleadas

La regla común de todos los planes: **contención primero, correcciones con red de tests, migraciones incrementales con rollback y cero ruptura de contratos con el frontend**.

| Ola | Nombre | Contenido | Horizonte |
|-----|--------|-----------|-----------|
| **0** | **Contención** | Rotación de secretos (orden: SMTP/RAE/MySQL/Mongo → cuenta admin → `JWT_SECRET` al final), bloqueo de red de prefijos admin, `JWT_SECRET` fail-fast, CORS allowlist, auth admin en modo shadow, `force=false`, quick wins de eficiencia (RAE sin `time.sleep`, `to_thread`, proyección en `get_current_user`, seeds check-first), script `audit_consistencia.py`. | 48 h – 1 semana |
| **1** | **Red de seguridad + críticos** | Testing Fase 0 (conftest, DB efímera, factories, `xfail` estricto) + tests de regresión de cada P0; CR-05 (account takeover), CR-06/IDOR de `user_attempts` con scoring server-side e `$inc` idempotente; admin auth en modo *enforce* (depende de SPA); PIN hasheado con bloqueo; rate limit confiable; registro atómico (upsert + `DuplicateKeyError`); guardas del narrativo; `/health/db`. | Semanas 1–3 |
| **2** | **Integridad y modelo de datos** | Optimistic locking (`version` en `narrative_runs`), counters y reserva de IDs, TZ `America/Argentina/Buenos_Aires`, migración `usuarios.progresos` → colección de progreso (Opción C) y puntos derivados (Σ score), invitados con identidad propia (IDs negativos por cookie/header), volumen para imágenes, ETL con dry-run/checkpoint, generación mensual en background con lock por mes, RAE async con caché de dos niveles, cachés acotadas. | Semanas 3–8 |
| **3** | **Modularización y servicios** | Plan 01 F1–F6 (duplicación narrativa, lógica fuera de routers, god files, ECA decidido, docs vivas) + Plan 04 F0–F2 (contrato congelado, `services/auth|cursos|juegos`, `AuthProvider`, `SERVICE_ROLE`, 3 contenedores + Caddy por prefijos, rollback a `backend-all`). | Semanas 6–16 |
| **4** | **Madurez** | Plan 04 F3–F5 (JWKS contra Auth externo, introspección selectiva, migración de datos por servicio, limpieza), seguridad F4 (SAST/DAST/pentest), testing con CI y cobertura ratchet (35→50→60%), opcional: replica set de 1 nodo para transacciones y Redis si la escala lo pide. | Mantenimiento |

---

## 2. Camino crítico y dependencias entre planes

1. **Contrato del micro de Auth + ventana de actualización de la SPA admin (Bearer)**: es la ruta crítica compartida de los planes 03, 04 y 01. Sin eso no se puede pasar el admin a *enforce* ni avanzar a F3 del plan 04.
2. **Migración de `usuarios.progresos` (plan 02, ola 2)** es prerrequisito de la separación de datos del plan 04 (F4).
3. **Testing Fase 0 (plan 06)** habilita la regla "ningún fix P0 se mergea sin su test de regresión" — conviene arrancarla en paralelo con la ola 0.
4. **Rotación de `JWT_SECRET` al final** de la secuencia de rotaciones (el valor viejo debe considerarse comprometido) y coordinada con la expiración/revocación de tokens.
5. **Eficiencia (plan 05)** aporta piezas que habilitan N>1 workers y los despliegues separados (locks en Mongo, generación en background, cachés acotadas).
6. **Arquitectura (plan 01)** ubica cada módulo desde ya en su *bounded context* destino (Auth/Cursos/Juegos) para no refactorizar dos veces con el plan 04.

---

## 3. Esfuerzo estimado por plan

| Plan | Estimación declarada | Nota |
|------|---------------------|------|
| 01 — Arquitectura | ≈ 45–70 jornadas (9–14 semanas, 1 dev) | Sin contar contenido nuevo |
| 02 — Persistencia | ≈ 45–60 jornadas (~9–12 semanas, 1 dev; ~5–7 con 2) | Incluye migración de progresos |
| 03 — Seguridad | ≈ 35–45 jornadas backend + 8–15 front/ops (8–10 semanas) | Camino crítico 2–3 semanas |
| 04 — Microservicios | ≈ 18–30 semanas-persona (3–6 meses) | 20 WPs; ruta crítica: contrato Auth + ventana SPA |
| 05 — Eficiencia | ≈ 4–6 semanas-persona (0–2); 6–9 con F3 | Quick wins en 2–4 días |
| 06 — Testing | ≈ 17–24 jornadas | En paralelo a los fixes |

**Las cifras no se suman linealmente**: hay solapamientos fuertes (06 acompaña a todos; 01 y 04 comparten refactor; 03 y 05 comparten rate limit y RAE). Suma bruta orientativa: ~250–400 días-persona para el programa completo. Lectura realista: olas 0–1 en 2–3 semanas, ola 2 en 5–8 semanas más, ola 3+ en 2–4 meses con equipo dedicado.

---

## 4. Decisiones bloqueantes (antes de implementar)

Consolidadas de las secciones de preguntas abiertas de cada plan. Las más urgentes:

| # | Decisión | Plan(es) | Default propuesto |
|---|----------|----------|-------------------|
| D1 | ¿Cómo autentica la SPA admin? (Bearer+storage / cookie httpOnly+CSRF / proxy que inyecta) | 01, 03, 04 | Bearer + storage a corto plazo, cookie httpOnly como objetivo |
| D2 | Dominios reales para CORS allowlist | 01, 03 | Definir lista por entorno (dev/staging/prod) |
| D3 | Contrato de invitados anónimos (¿ID propio? ¿efímero?) | 01, 02 | IDs negativos reservados por cookie/header |
| D4 | ECA del narrativo: ¿completar `AMORTIGUAR_DANIO`/triggers o retirar y documentar? | 01 | Decidir con producto |
| D5 | Transacciones: ¿Opción A (replica set 1 nodo) ahora o Opción B/C primero? | 02 | B y C ahora; A como decisión de fase 3 |
| D6 | ¿Una base con owners lógicos o bases separadas por servicio? | 04 | Una base, bases lógicas en F4 |
| D7 | ¿Monorepo con `services/*` o repos separados? | 04 | Monorepo primero; repos con equipos dedicados |
| D8 | ¿Cuándo entra Redis? | 05 | Solo si la escala lo exige; leases en Mongo mientras |
| D9 | Contrato con el micro de Auth (claims `id`, `tipoUsuario`/rol, `tv`; endpoints S2S) | 04 | Tomar la propuesta del anexo del plan 04 como base de negociación |
| D10 | Ventana y alcance de la migración de datos (`progresos`, `puntos`, counters) | 02, 04 | Migración one-shot validable con snapshot + dry-run + reconciliación |

Las listas completas están en la sección de preguntas abiertas de cada plan (15 en 01, 12 en 02, 14 en 03, 20+8 en 04, 14 en 05, varias en 06).

---

## 5. Reglas de oro para la ejecución (propuestas por los planes)

1. **Ningún fix P0 sin test de regresión** (regla del plan 06: tests con `xfail` estricto escritos antes del fix).
2. **No romper contratos**: los 82 endpoints + 4 de sistema + 2 mounts mantienen método, ruta y payload; el gateway absorbe el rearquitecto ("el frontend no nota nada").
3. **Cambios peligrosos con transición**: feature flags (`ADMIN_API_AUTH_MODE`, `AUTH_PROVIDER`, `RAE_ENABLED`), modo shadow antes de enforce.
4. **Migraciones con snapshot → dry-run → apply con checkpoint → validación → ventana dual → retiro**, siempre con rollback documentado.
5. **Una fuente de verdad por dato** (progreso, puntos, identidad de invitados) y referencias externas por `usuarioId`.
6. **Medir después de implementar**: métricas M1–M14 del plan 05 y script `audit_consistencia.py` del plan 02 como red de seguridad continua.

## 6. Próximos pasos sugeridos

1. Revisar los planes y responder las decisiones bloqueantes (mínimo D1, D2, D3, D9 para desbloquear las olas 0–2).
2. Con el OK, ejecutar la **Ola 0 (contención)**: rotaciones operativas + cambios de bajo riesgo, en paralelo con la Fase 0 de testing.
3. Seguir con las olas 1→4 según el roadmap, validando puertas de salida por fase.

## 7. Limitaciones

- Documentos de planificación: describen cambios propuestos, no aplicados ni verificados en runtime.
- Las estimaciones son relativas (S/M/L escaladas a jornadas aproximadas) y pueden variar ±50%.
- El plan 04 asume un contrato razonable para el micro de Auth (no disponible su código): la sección de contrato tentativo está pensada para negociar, no como verdad.
- No se expusieron valores del `.env` real en ningún documento.
