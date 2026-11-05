# N0 — Alinear bases, contrato y caracterización

## Rol y misión

Actuá como responsable de contratos backend y de caracterización del narrativo. Cuando el usuario solicite ejecutar N0, establecer una base verificable para la migración sin implementar todavía comandos, reglas nuevas ni cambios de acceso. El resultado debe permitir que las etapas posteriores distingan capacidades existentes, defectos reproducidos y decisiones pendientes.

Leer primero la [guía común](00-guia-de-ejecucion.md) y las secciones 2, 5–7 y N0 de la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md). Aplicar sus paradas y restricciones aunque no se repitan aquí.

## Contexto y fuentes de entrada

El backend de referencia es `JNicolasFernandezG/juegos-mayores-actualizaciones-back`, rama `main`, identificado por el usuario. El corte remoto verificado al redactar era `9cb670c`; el checkout local `7b86563` solo agregaba diferencias del build admin. Revalidar ambas referencias. No afirmar qué SHA está desplegado sin evidencia del artefacto/proceso autorizado.

El análisis original usó el fork educativo `33cdf8f`; las afirmaciones de ausencia de narrativa, economía o SSO no se trasladan al backend de juegos. La separación dominio/presentación es una propuesta válida, pero las fases, OCC y ledger ya existen.

Entradas, relativas a B definido en la guía:

- B: `app/main.py`; `app/features/narrative/schemas/game_schemas.py`; `game/router.py`, `game/identity.py`, `game/run_repository.py`, dentro de la misma feature.
- B: `tests/conftest.py`, `pytest.ini`, `app/core/database.py`, `app/core/config.py`; localizar tests de contrato narrativo y snapshot OpenAPI.
- B: `docs_interna/refactor/05-plan-solucion.md`, `docs_interna/refactor/adr/0001-arquitectura-objetivo.md`, `docs_interna/GUIA_CAMBIOS_BACKEND_FRONTEND.md`.

Las rutas abreviadas de `game/` pertenecen a `app/features/narrative/`. Verificar símbolos y DTOs completos; no concluir equivalencia de contratos a partir de sus nombres. El consumo frontend es evidencia externa de solo lectura cuando resulte necesaria; N0 no modifica ese repositorio ni genera sus tipos.

## Dependencias y alcance

N0 no depende de otra etapa. Requiere acceso de lectura al checkout backend y permiso del usuario para ejecutarla; cualquier evidencia de consumidores es externa y de solo lectura. Puede producir fixtures y contratos aprobados, pero no habilitar un protocolo incompleto ni un endpoint público de prueba.

No alterar scoring, probabilidades, cantidades, adaptación, identidad o despliegue como parte de «alinear». No actualizar snapshots de contrato mecánicamente para esconder incompatibilidades. La corrección editorial integral del HTML pertenece a N9; aquí registrar la diferencia de base y el contrato objetivo.

## Paradas obligatorias

- **D01/D02:** antes de generar tipos objetivo o rutas, preguntar qué superficie de API, errores y modelo de resultado/continuación se aprueban. Presentar matriz observable, no elegir `/v3` por conveniencia.
- **D03/D07:** antes de cambios de identidad/reinicio, preguntar cómo se conserva el invitado, qué ocurre con JWT inválido y qué reinicios remotos se permiten bajo la política sin replay.
- **D04–D06:** antes de convertir una conducta local en regla backend, consultar duplicados/copias, pesos 0%, edad y selección automática. No pedir aprobación de datos que se puedan comprobar en código: presentar primero el comportamiento real.
- **D08/D09:** antes de cerrar el contrato durable, acordar requisitos de almacenamiento, recibos/recompensas y publicación versionada. Las capacidades técnicas de Mongo se investigan; su ausencia no autoriza modificar infraestructura.
- Si no puede garantizarse una base efímera: detener pruebas con DB. Si obtener evidencia de despliegue exige credenciales/acceso no autorizado: declarar desconocido, sin bloquear la caracterización puramente local.

No es necesario resolver todas las decisiones para iniciar lecturas; indicar cuál bloquea cada entrega y mantener las otras como pendientes.

## Secuencia de trabajo

1. Verificar estado del backend, remotos y referencias. Identificar cambios ajenos y diferencias relevantes frente a `main` productivo, sin sincronizar ramas. Separar SHA remoto, checkout y despliegue observado; no modificar ni validar clientes ajenos.
2. Inventariar endpoints, motor y DTOs realmente consumidos. Mapear entrada, identidad, guardas de fase, escritura, versión y salida; distinguir V1 plano de grafos V2 y API de motor.
3. Corregir primero el aislamiento local de tests: validar host/base efectivos de URI antes de conectar o inicializar índices; separar cliente ASGI sin DB cuando corresponda. Agregar pruebas que rechacen URI/base equivocadas sin intentar conexión. No cambiar configuración productiva ni volcar secretos al reporte.
4. Crear fixtures mínimas propias para selección, pasivas, pérdidas, afinidad cero, tags, duplicados, pesos, especiales, mes 12 y demo. Clasificar cada expectativa como comportamiento preservado o reproducción de defecto; no legitimar el defecto como contrato futuro.
5. Presentar el contrato objetivo: creación idempotente por principal/slot; mutaciones por run/generación con `commandId`, `expectedVersion` y payload discriminado; snapshot completo; consecuencias, resultado y recompensa recuperables. Definir errores de validación, autenticación, propiedad, versión y clave reutilizada. Completo significa suficiente para reanudar, no todo el catálogo fijado: excluir semillas, destinos ponderados, nodos futuros y secretos no permitidos de snapshots y recibos.
6. Resolver las paradas aplicables. Solo después de D01/D02 aprobadas, preparar DTOs y OpenAPI backend con test de deriva. No generar tipos de cliente ni publicar comandos sin implementación ni prometer rutas como soportadas.
7. Entregar matriz de decisiones y pruebas que habilitan N1/N2/N3. Señalar dependencias aún abiertas sin avanzar automáticamente a ellas.

## Pruebas y aceptación

- [ ] Procedencia corregida y respaldada por SHAs actuales; despliegue confirmado o explícitamente desconocido.
- [ ] La suite no puede crear índices en una base distinta por prevalencia de la URI.
- [ ] Caracterización de V1/V2 diferencia API, motor y protocolo; no elimina el contrato anterior.
- [ ] Cada cambio de semántica tiene una decisión aprobada o una parada pendiente identificada.
- [ ] Fixtures propias cubren mes 12, identidad invitada, afinidad cero, resultado neutral y duplicados.
- [ ] Contrato aprobado permite reanudación sin catálogo admin ni segunda autoridad frontend; pruebas de proyección excluyen semillas, destinos, nodos futuros y secretos no autorizados.
- [ ] Tipos generados, si se aprobaron, tienen origen reproducible y comprobación de deriva.

## Entrega y traspaso

Seguir la entrega estándar de la guía. Incluir tabla «hecho observado / requisito / decisión / evidencia / etapa responsable» y especificar qué gates de N1/N2/N3 están satisfechos. Si el contrato sigue pendiente, entregar diagnóstico y preguntas: no declarar N0 completa ni inventar aprobación para desbloquear el desarrollo.
