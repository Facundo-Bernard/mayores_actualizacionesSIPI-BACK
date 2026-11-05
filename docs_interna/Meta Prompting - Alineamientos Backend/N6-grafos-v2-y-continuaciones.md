# N6 — Grafos V2 y continuaciones

## Rol y misión

Al invocarse esta etapa, integrá grafos V2 al coordinador común y conservá cada resultado antes de su continuación. Tratá los grafos como escenas, no como finales globales. Implementá únicamente decisiones aprobadas; este prompt no habilita producción ni convierte V2 en motor oficial.

## Lectura obligatoria

Leé completas la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) y la [guía común](./00-guia-de-ejecucion.md), con foco en N1–N6 y aceptación. Revisá la entrega de [N5](./N5-inicio-y-flujo-v1.md), no solo su prompt.

B = `C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK`. Revalidá rutas y líneas por símbolos; la integración de clientes es evidencia externa, no una asignación de implementación:

- B:`app/features/narrative/game/motor_v2/graph_engine.py`: `GraphTraversalEngine`, `iniciar_grafo_en_partida`, `avanzar_nodo`, `_detectar_cruces_afinidad`, `_encadenar_especial_pendiente`.
- B:`app/features/narrative/game/motor_v2/v2_graph_service.py`: `avanzar_nodo_v2`, `_exigir_partida_v2_en_fase`; B:`app/features/narrative/game/turn_state.py`: `obtener_turno_actual`.
- B:`app/features/narrative/constants.py`: `AFINIDAD_UMBRAL_LEALTAD`, `AFINIDAD_UMBRAL_TRAICION`; B:`app/features/narrative/validation/graph_validator.py`: `validar_grafo`.
- B:`scripts/v2_readiness.py`: `aplicar_impactos`, `_estado_sintetico`, `simular_universo`.
- B:`app/features/narrative/schemas/v3_contract_schemas.py` y `v3_openapi.py`: resultado, continuación y proyecciones anti-spoiler del contrato objetivo.

## Contexto verificado versus hipótesis

El corte 2026-11-05 contiene grafos, opciones condicionadas y destinos ponderados. Inicio y encadenamiento realizan escrituras separadas; un terminal puede ser sustituido por la raíz siguiente. Son hallazgos a revalidar, no garantías de persistencia actuales.

Los umbrales existentes son lealtad 95 y traición 15: cruce desde menos de 95 hasta al menos 95, y desde al menos 15 hasta menos de 15. Hay cola de especiales y conversación incidental al 40% desde terminal de tipo evento; sus disparos/orden deben caracterizarse, no reinterpretarse.

Producción fue identificada por el usuario como `JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, `main`; la diferencia conocida con la rama local era build admin. No prueba el SHA desplegado. Revalidá HEAD y fuentes; `AVANZAR_NODO`/`CONTINUAR_RESULTADO` son nombres objetivo sujetos al contrato aprobado.

## Dependencias y evidencia requerida

Exigí N4 aprobado y modelo D02 de resultado implementado en N5, más CAS/recibos/RNG D08 y revisiones N3. Solicitá pruebas de atomicidad real, snapshot desde una lectura y continuidad reanudable, con símbolos actuales. Si faltan, prepará solamente fixtures y pruebas aisladas independientes. No crees un segundo almacenamiento para completar N6.

## Alcance y exclusiones

Conservá límites, triggers, pools, reciclaje y duración vigente de doce meses. No aplanes grafos ni rediseñes editor, scoring, ledger o economía invitada. No autorices arranques manuales como bypass de guardas. Conservá contratos legacy sin permitirles mutar runs nuevos según el discriminador aprobado. Preservá B:`app/static/admin/test-narrativo.html`. Respetá cambios ajenos; sin commit/push/sync, infraestructura, permisos ni DB compartida no autorizados.

## Paradas obligatorias y preguntas específicas

Consultá solo decisiones no resueltas por aprobación; todos los IDs parten pendientes.

- **Antes del paso 2, D02:** ¿qué representación de terminal, secuencia pendiente y continuación comparte N5/N6? ¿Cómo conviven resultado de escena y final global sin perder texto?
- **Antes del paso 3, D05:** ¿se aprueba preservar pools, agotamiento/reciclaje, disparos y orden caracterizados? ¿Qué discrepancias requieren corrección explícita? No cambies 95/15, 40% ni doce meses por inferencia.
- **Antes del paso 3, D04:** si impactos V2 divergen del contrato común, ¿qué semántica de ausentes, orden y redondeo queda aprobada? No homogeneices silenciosamente.
- **Antes del paso 4, D09:** ¿qué revisión/publicación permite seleccionar grafos y qué tratamiento aprobado corresponde a catálogos inválidos, especiales faltantes o cadenas imposibles?

Detené la parte bloqueada; avanzá solo inspección/tests aislados independientes, nunca contenido de reemplazo, probabilidades provisionales ni garantías menores.

## Secuencia numerada

1. Caracterizá nodos intermedios, terminales, colapso, especiales múltiples, conversación opcional y agotamiento. Separá comportamiento vigente de defectos.
2. Llevá avance al coordinador aprobado: validar propietario, motor, fase, grafo, nodo, opción y versión. Calculá en memoria; confirmá estado, resultado, continuación y recibo una sola vez.
3. Capturá consecuencias reales al ejecutar. Conservá terminal con ID/texto estable, incluso sin deltas. Reconocerlo explícitamente habilita la escena pendiente sin repetir azar ni efectos. Mantené cierre global en lógica común.
4. Leé contenido fijado y validado. Proyectá únicamente opciones permitidas; ocultá semillas, destinos ponderados y secretos futuros. GET rehidrata desde una versión sin consultar resultados V1 para nodos V2.
5. Conservá cruces y cola de especiales, incluidos disparos desde otros especiales, según caracterización aprobada. No inventes conversación posterior para compensar encadenamientos. Cerrá caminos sin conversación sin soft-lock.
6. Integrá proyección y reanudación backend: GET no ejecuta negocio y toda transición exige un comando explícito. Ejecutá aceptación aislada y traspasá fixtures/contrato a N7/N8.

## Pruebas y criterios de aceptación

- [ ] Repetición, conflicto y caída entre preparación/commit no dejan punteros parciales ni duplican impactos.
- [ ] Recarga en nodo/terminal conserva contenido, saldo, resultado neutral y continuación; reconocimiento repetido no muta nuevamente.
- [ ] Casos 94→95, 95→95, 15→14 y 14→14 distinguen cruce de permanencia; se preservan disparos y orden.
- [ ] Opciones bloqueadas/ocultas, especiales encadenados, agotamiento/reciclaje y ausencia de conversación no generan soft-lock.
- [ ] E2E HTTP de doce meses V2, cuenta/invitado, pasivos y cierre económico común pasa en Mongo efímero; readiness sintético no lo sustituye.
- [ ] Validá URI, hosts y base efectiva antes de conectar/índices. La aceptación UI es externa; no la certifiques desde fixtures ni readiness backend.

## Entrega y traspaso

Entregá cambios, matriz de transiciones, decisiones abiertas y evidencia reproducible. Separá readiness, pruebas puras, integración y E2E. Informá a N7 cómo renderizar cada escena pendiente y a N8 qué discriminadores/revisiones exige V2; no declares rollout autorizado.
