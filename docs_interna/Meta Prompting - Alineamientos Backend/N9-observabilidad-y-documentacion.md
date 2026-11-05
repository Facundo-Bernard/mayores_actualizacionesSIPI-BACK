# N9 — Observabilidad y documentación

## Rol y misión

Cuando se invoque esta etapa, instrumentá diagnóstico verificable y alineá la documentación backend y el paquete contractual con lo realmente soportado. Diseñá observabilidad desde N0; cerrá N9 solo después de N8. No confundas documentación, pruebas locales y despliegue ni des por aprobadas decisiones pendientes.

## Lectura obligatoria

Leé completas la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) y la [guía común](./00-guia-de-ejecucion.md). Revisá evidencias finales N0–N8 y [N8](./N8-migracion-y-reversion.md), distinguiendo prompt de entrega ejecutada.

B = `C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK`. Localizá responsabilidades por símbolos/secciones y revalidá líneas:

- B:`app/main.py`: `lifespan`, `global_fail_closed_exception_handler`; B:`app/features/narrative/game/run_repository.py`: `persistir_run`.
- B:`app/features/narrative/game/endings_service.py`: `sincronizar_intento_usuario`; B:`app/shared/ledger.py`: `MongoPointsLedger`, `reconcile_pending_ledger`.
- B:`app/features/narrative/validation/graph_validator.py`: `validar_grafo`; B:`scripts/v2_readiness.py`: `simular_universo`.
- B:`app/static/admin/test-narrativo.html`: diagnóstico admin existente, sin compilar ni modificar clientes externos.

La documentación y los laboratorios frontend pertenecen a su responsable; N9 actualiza únicamente fuentes backend y el paquete contractual de integración.

## Contexto verificado versus hipótesis

La auditoría del 2026-11-05 corrigió una comparación contra el backend educativo `Facundo-Bernard/mayores_actualizacionesSIPI-BACK@33cdf8f`, no contra el backend de juegos. El usuario identifica producción como `JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, `main`; el main remoto comprobado era `9cb670c` y HEAD local `feature/refactor-backend` era `7b86563`, con diferencia solo de build admin. No certifican despliegue.

Hay logging y ledger existentes; no presupongas plataforma de métricas, recibos narrativos nuevos ni contrato v3 implementados. El laboratorio tenía diez pruebas acotadas, no aceptación Mongo/browser. Revalidá fuentes y HEAD actuales; no presentes cantidades históricas de pruebas como evidencia vigente.

## Dependencias y evidencia requerida

Exigí contrato/errores D01, estados/resultados D02, identidad D03, almacenamiento/recibos/recompensas D08, revisiones D09 y rollout/reversión D10 explícitos. Para cierre, requerí N8 ensayado y matriz de pruebas con ejecutadas, fallidas y no ejecutadas. Podés preparar esquema diagnóstico con fixtures antes, pero no declarar operación final. Pedí artefactos/logs de despliegue autorizados si se pretende describir producción; su ausencia debe quedar visible.

## Alcance y exclusiones

Instrumentá sobre mecanismos existentes y actualizá documentos backend y el paquete contractual coordinando cambios concurrentes. No reescribas la revisión histórica para que parezca actual: agregá revisión claramente delimitada. Excluí nuevo vendor, infraestructura, rediseño del visor, scoring, editor, economía guest servidor y cambios en repositorios de clientes. No crees ledger paralelo. Sin autorización, no modifiques permisos/configuraciones, DB compartida, commit/push/sync ni despliegues. No sobrescribas ediciones ajenas; mantené B:`app/static/admin/test-narrativo.html` en builds admin autorizados.

## Paradas obligatorias y preguntas específicas

Los IDs permanecen pendientes hasta aprobación explícita; no preguntes hechos verificables leyendo código.

- **Antes del paso 2, D11/D03:** ¿qué campos correlacionables, retención, acceso, muestreo y tratamiento de identificadores se autorizan? ¿Qué destinos existentes pueden recibirlos sin tokens ni datos personales?
- **Antes del paso 3, D11/D08:** ¿qué métricas, umbrales y retención diferencian conflicto, repetición y liquidación pendiente/fallida? ¿Cómo consultar recibos autorizados sin cambiar su retención para facilitar observabilidad?
- **Antes del paso 4, D01/D02/D09:** ¿están aprobados los contratos, fases y publicación/revisiones que se documentarán como soportados? Si faltan, mantenelos como propuesta, no cierres IDs automáticamente.
- **Antes del paso 5, D10:** ¿qué evidencia permite afirmar cohorte activa o reversión ensayada/desplegada? ¿Qué actualización de documentación backend y paquete contractual está autorizada?

Si falta aprobación, avanzá solo inspección/tests aislados independientes. No agregues proveedor provisional, datos sensibles ni garantías rebajadas.

## Secuencia numerada

1. Inventariá logs, manejo de errores, reconciliador y documentación. Construí matriz evidencia→afirmación distinguiendo diseño, implementación, aceptación y despliegue; registrá discrepancias sin alterar historia.
2. Instrumentá resultado del comando, CAS, motor y versiones de dominio/reglas/contenido. Correlacioná run/comando solo en logs bajo D11; excluí tokens, credenciales, payloads personales, semillas y contenido secreto. Sanitizá también excepciones y rechazos.
3. Medí conflictos, repeticiones, latencia, rechazos, resultados pendientes y liquidaciones pendientes/fallidas. Usá etiquetas acotadas: nunca `runId`/`commandId` ni identificadores arbitrarios de alta cardinalidad. Separá intentos de confirmaciones y fallos confirmados de commit incierto; no dupliques efectos al observar.
4. Probá diagnóstico ganador/perdedor: ganador recupera recibo; perdedor no publica consecuencias ni acredita puntos. Mostrá reconciliación de respuesta perdida y cierre sin asiento, reutilizando garantías existentes, no reejecutando negocio.
5. Actualizá HTML y Markdown backend contra el HEAD real, incluyendo capítulos/contratos afectados, no solo hashes. Conservá procedencia educativa como histórica. Explicá problema→solución→acción, API versus motor V1/V2, snapshot autoritativo, demo explícita y recuperación con misma clave/payload.
6. Ajustá los diagnósticos backend para no enseñar recibos sin hash, resultados volátiles o fallback automático. Delimitá qué prueban; mantené guía de reproducción, límites de readiness y operación/reversión autorizada. Verificá enlaces y preservación del diagnóstico admin.

## Pruebas y criterios de aceptación

- [ ] Comando incierto se diagnostica por versión/CAS/recibo sin consultar capturas ni repetir efectos; recibo antiguo conserva evidencia sin regresar snapshot.
- [ ] Logs excluyen tokens/datos personales; métricas evitan alta cardinalidad; fallos de instrumentación no cambian dominio.
- [ ] Repetición, conflictos y liquidación diferencian hechos confirmados; recompensa guest local deduplicada por `rewardId`, sin reacreditar slot.
- [ ] Documentos distinguen propuesta, soporte y despliegue; preservan historia y reflejan el backend y su contrato real.
- [ ] Mongo de pruebas valida URI/hosts/base efectiva antes de conexión/índices; usá instancia efímera dedicada. Mocks/readiness no certifican doce meses E2E.
- [ ] Pruebas UI/admin requieren devserver/browser; declaralos ausentes si corresponde. No relajes autenticación ni borres `test-narrativo.html` para pasar builds/tests.

## Entrega y traspaso

Entregá rutas modificadas, eventos/métricas aprobados, consultas diagnósticas sanitizadas y evidencia reproducible. Enumerá decisiones/bloqueos pendientes y pruebas no ejecutadas. Cerrá solo el alcance comprobado; no marques etapas del coordinador ni afirmes producción certificada sin evidencia.

Traspasá a [N10 — HTML integral del backend](N10-documentacion-html-backend.md) el inventario de módulos/contratos, las evidencias de pruebas, decisiones y correspondencias con el documento recibido. N10 creará una referencia HTML nueva y exclusiva del backend; no sustituye la actualización de fuentes/documentos de N9 ni se ejecuta automáticamente al completar esta etapa.
