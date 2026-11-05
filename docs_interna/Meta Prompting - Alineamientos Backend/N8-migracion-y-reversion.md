# N8 — Migración y reversión

## Rol y misión

Implementá únicamente herramientas locales de dry-run y ensayo cuando se invoque esta etapa. Prepará migración, convivencia y reversión verificables; no ejecutes migraciones, rollout ni operaciones productivas por defecto. Separá aprobación del diseño, permiso de ejecución y autorización de producción.

## Lectura obligatoria

Leé completas la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) y la [guía común](./00-guia-de-ejecucion.md). Exigí entregas y aceptación de [N5](./N5-inicio-y-flujo-v1.md), [N6](./N6-grafos-v2-y-continuaciones.md) y [N7](./N7-frontend-autoritativo-y-demo.md).

B = `C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK`. Revalidá líneas mediante símbolos:

- B:`app/features/narrative/game/run_repository.py`: `crear_run`, `_filtro_version`, `persistir_run`.
- B:`app/features/narrative/game/setup_service.py`: `iniciar_partida`, `reiniciar_partida`; B:`app/features/narrative/game/router.py`: `endpoint_reiniciar_partida`, `endpoint_v2_avanzar_nodo`.
- B:`app/features/narrative/game/endings_service.py`: `sincronizar_intento_usuario`; B:`app/shared/ledger.py`: `reconcile_pending_ledger`.
- B:`app/core/database.py`: `connect_to_mongo`, `init_indexes`; B:`scripts/v2_readiness.py`: `ejecutar_dry_run`.

La matriz de clientes y la evidencia de integración son entregas del responsable frontend; N8 no modifica ese repositorio.

## Contexto verificado versus hipótesis

El usuario identificó `https://github.com/JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, rama `main`, como backend de producción. El 2026-11-05, `ls-remote` verificó `9cb670ca4fdc16b9940fa84d8204eb66bdd94b46`; HEAD local `feature/refactor-backend` era `7b865637756cbf28add5899c2fd053c927254bb4`. El diff era solo build admin, no lógica. Ningún dato certifica el despliegue.

Revalidá procedencia y estado del backend sin sincronizar; la compatibilidad de clientes se incorpora como evidencia externa. El código histórico interpreta ausencia de versión como cero y reinicio elimina la run. No confundas esa representación con esquema nuevo ni presupongas un migrador implementado. Cohortes, conversión activa y recuperación ambigua son propuestas pendientes.

## Dependencias y evidencia requerida

Exigí N5/N6/N7 y validación integral: doce meses V1/V2, CAS/recibos, identidad, contenido fijado, recompensa recuperable y recuperación documentada para consumidores. Pedí resultados reproducibles, contratos reales y matriz cliente/protocolo/motor aportada como evidencia externa, no solo readiness. Exigí evidencia de discriminador persistido y de bloqueo de mutaciones legacy sobre runs nuevas antes de habilitar altas nuevas. La aceptación de N2/N3 debe cubrir índices, revisiones y retención reales.

## Alcance y exclusiones

Por defecto trabajá con fixtures sintéticos/exportaciones sanitizadas autorizadas y pruebas puras; dry-run no escribe ni crea índices. No presupongas permiso para leer DB compartida. No conviertas runs antiguas automáticamente, alternes motor/protocolo ni reconstruyas historia inventada. No sobrescribas trabajo ajeno, cambies permisos/configuración/infraestructura o hagas commit/push/sync. Preservá B:`app/static/admin/test-narrativo.html` en builds autorizados. No crees ledger nuevo ni economía guest servidor.

## Paradas obligatorias y preguntas específicas

Todos los IDs quedan pendientes hasta aprobación explícita documentada.

- **Antes del paso 2, D10/D01:** ¿se aprueba convivencia por discriminador persistido? ¿Qué cohorte, criterios de entrada/salida, compatibilidad y retiro de contrato se autorizan?
- **Antes del paso 3, D09/D02:** ¿se permite convertir runs activas y en qué frontera segura? ¿Cómo tratar contenido histórico inexistente y resultados ambiguos sin resorteo ni efectos repetidos?
- **Antes del paso 3, D07/D08:** ¿qué generación, retención de recibos y tratamiento de obligaciones pendientes se preservan? ¿Cómo se mantiene `rewardId` sin reacreditar el mismo slot?
- **Antes del paso 4, gate de ejecución D10/D03:** ¿qué entorno, URI/base, datos, operación exacta, copia y restauración están autorizados? Detené conexiones/índices/escrituras hasta confirmación, incluso para ensayo con DB.
- **Antes de cualquier activación real posterior al paso 5, gate producción D10:** ¿qué build servido, ventana, responsables, cohorte y umbrales habilitan ejecución y reversión? Aprobar ensayo no autoriza producción ni infraestructura.

Si hay bloqueo parcial, avanzá solo inspección/tests aislados independientes; nunca migración aproximada, rutas de escape legacy ni relajación de garantías.

## Secuencia numerada

1. Inspeccioná repositorios y herramientas existentes; implementá el mínimo local reutilizable. Definí salida diagnóstica sin datos personales y ejecución dry-run por defecto.
2. Inventariá activas/finales, versiones, contenido faltante, resultados ambiguos y liquidaciones incompletas con datos autorizados. Diferenciá conteos comprobados de desconocidos; no completes información ausente por conjetura.
3. Prepará plan determinista e idempotente. Las antiguas terminan bajo contrato anterior; nuevas fijan protocolo/reglas/contenido. Si se aprueba conversión, exigí frontera segura, copia y equivalencia. Sin revisión histórica, declarás fijación del contenido disponible al migrar, no reconstrucción del pasado.
4. Tras gate explícito, ensayá en base efímera dedicada: validá URI, hosts y base efectiva antes de conexión/índices, no solo `MONGODB_DB_NAME`. Probá interrupción, reanudación y restauración. Prepará índices/revisiones antes de altas y verificá clientes abiertos.
5. Ensayá reversión: detener altas nuevas y conservar servidor capaz de terminar runs nuevas y liquidarlas. Nunca enviarlas a servicios viejos, bajar versiones ni sobrescribir estado; no rerun de azar para recuperar terminales.
6. Prepará propuesta de cohorte y checklist de operación, sin activarla. Condicioná retiro legacy a ausencia demostrada de runs/clientes dependientes; deprecación no elimina V1.

## Pruebas y criterios de aceptación

- [ ] Dry-run repetido no altera datos; informes distinguen ambiguos y bloqueos.
- [ ] Conversión autorizada es idempotente, auditable y equivalente; no inventa consecuencias/revisiones históricas.
- [ ] Clientes antiguos no mutan runs nuevas; protocolo/motor permanecen fijados.
- [ ] Fallo parcial, restauración y reversión preservan continuidad, recibos y recompensa única, incluida deduplicación local guest por `rewardId`.
- [ ] Reversión detiene altas, no soporte de runs nuevas; E2E doce meses supera readiness sintético.
- [ ] UI requiere devserver/browser: documentá si no está disponible y mantené aceptación pendiente.

## Entrega y traspaso

Entregá herramientas locales, resultados del ensayo autorizado, bloqueos y gates pendientes. Identificá claramente lo no ejecutado y remití a N9 matriz de compatibilidad y procedimiento de recuperación. No declares producción migrada, revertida ni despliegue certificado.
