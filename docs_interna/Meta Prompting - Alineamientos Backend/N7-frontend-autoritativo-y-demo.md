# N7 — Paquete backend de integración y demo explícita

## Rol y misión

Al invocarse N7, entregá el paquete backend que permite a un consumidor externo integrarse con el protocolo confirmado: OpenAPI vigente, ejemplos, errores, recuperación y límites de compatibilidad. El backend es la única autoridad de las partidas remotas; la presentación y la FSM del cliente pertenecen a su responsable. No interpretes la invocación como aprobación de despliegue ni de decisiones pendientes.

## Lectura obligatoria

Leé completas la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) y la [guía común](./00-guia-de-ejecucion.md). Contrastá entregas reales de [N5](./N5-inicio-y-flujo-v1.md) y [N6](./N6-grafos-v2-y-continuaciones.md), especialmente DTOs, errores, recibos y resultados.

B = `C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK`. Revalidá por símbolos:

- B:`app/features/narrative/schemas/v3_contract_schemas.py`: comandos, snapshot, consecuencias, resultado y recibo.
- B:`app/features/narrative/v3_openapi.py`: `build_narrative_v3_openapi`; B:`tests/contract/test_narrative_v3_contract.py` y snapshot asociado.
- B:`app/features/narrative/game/turn_state.py`: `obtener_turno_actual`; B:`app/features/narrative/game/run_repository.py`: `persistir_run`; B:`app/shared/ledger.py`: `MongoPointsLedger`.
- B:`app/static/admin/test-narrativo.html`: diagnóstico admin existente, sin convertirlo en cliente contractual del protocolo nuevo.

## Contexto verificado versus hipótesis

El contrato objetivo `/v3` se materializa como OpenAPI aislado y no público durante N0. Que exista ese artefacto no acredita handlers, persistencia, compatibilidad ni despliegue. Revalidá el FastAPI activo y las entregas N4–N6 antes de marcar una operación como soportada.

El usuario identifica producción como `JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, `main`; SHAs conocidos y diff solo admin no acreditan despliegue. La evidencia de consumidores es externa y de solo lectura: este repositorio no contiene la FSM de presentación ni la deduplicación visual.

## Dependencias y evidencia requerida

Exigí N4 y flujos N5/N6 implementados y probados antes de declarar soporte. Verificá identidad D03, semántica D02, contrato D01 y garantías D08: recibo autorizado antes de rechazar versión esperada, hash de payload y persistencia atómica. Si faltan, limitá la entrega a fixtures/contrato objetivo claramente marcados, sin publicar rutas incompletas.

## Alcance y exclusiones

Entregá artefactos backend versionados y reproducibles, ejemplos HTTP y pruebas de contrato. No edites frontend, instales sus dependencias, generes TypeScript, compiles clientes ni ejecutes pruebas UI. Excluí cambios de balance, economía guest servidor, nuevo ledger y migración automática local→remoto. No sobrescribas trabajo ajeno ni hagas commit/push/sync, cambios de permisos/configuración/infraestructura o DB compartida sin permiso. Preservá B:`app/static/admin/test-narrativo.html` al compilar admin si corresponde.

## Paradas obligatorias y preguntas específicas

Las decisiones aprobadas se aplican; solo se detiene una discrepancia nueva o una decisión aún pendiente.

- **D01/D02:** si la implementación difiere de la unión de contenido, fases, errores o resultado/continuación aprobados, no actualices el snapshot para ocultarla; proponé corrección o extensión y consultá el cambio semántico.
- **D03:** documentá únicamente el transporte efectivamente implementado. JWT inválido es 401 y nunca cambia a demo; no inventes emisión invitada si N1 no la entregó.
- **D08:** si retención, commit incierto o `rewardId` difieren del contrato, coordiná con N2 antes del paquete de recuperación. No diseñes almacenamiento alternativo.
- **D06/D07:** las runs nuevas no exponen adaptación de dominio mientras D06 siga diferida. Reinicio conserva generación nueva y recompensa única por slot; limpiar demo es una operación separada.
- **Antes de retirar compatibilidad, D10:** el retiro global pertenece a N8. Mientras siga pendiente, conservá el aislamiento legacy y limitá N7 al camino nuevo probado.

## Secuencia numerada

1. Compará FastAPI activo, contrato objetivo y entregas N4–N6. Clasificá cada operación como propuesta, implementada, probada o desplegada solo con evidencia correspondiente.
2. Generá el OpenAPI desde la fuente backend vigente y mantené su prueba de deriva. No registres en `app.main` rutas objetivo sin implementación ni edites snapshots mecánicamente.
3. Entregá ejemplos de creación, snapshot, cada comando y consulta de recibo, incluyendo selección inválida, propiedad, versión/generación, fase, clave reutilizada y commit incierto. La identidad nunca se declara en payload.
4. Documentá la proyección autoritativa: afinidad cero, tags completos, instancias de inventario, `completed/game_over`, contenido visible y comandos permitidos. Verificá que no expone semillas, destinos, nodos futuros ni catálogos admin.
5. Especificá recuperación: conservar clave/tipo/payload/versión, consultar recibo antes de versión, reintentar la misma intención y no regresar snapshots al aplicar un recibo antiguo. Ausencia de recibo no prueba que una operación en vuelo no confirme.
6. Documentá `rewardId`, canal ledger/local y liquidación como requisitos de integración. La acreditación local invitada se deduplica en el consumidor; N7 no implementa ese cliente ni otorga saldo invitado en servidor.
7. Delimitá demo y diagnósticos backend: entrada explícita, datos separados y ningún fallback automático desde error/red de una run remota. Entregá a N8 la matriz protocolo/motor y a N9 los casos de diagnóstico.

## Pruebas y criterios de aceptación

- [ ] OpenAPI y ejemplos tienen origen reproducible y prueba de deriva; el contrato objetivo no se presenta como API activa.
- [ ] Fixtures conservan cero, tags ausentes, copias por instancia, resultado neutral y victoria/derrota sin cálculo local.
- [ ] Repetición, CAS conflictivo, commit incierto, recibo tardío y snapshot viejo tienen ejemplos/pruebas HTTP acordes a la implementación real.
- [ ] Las proyecciones excluyen secretos y futuros; `rewardId` y estados económicos no confunden canal local con liquidación de ledger.
- [ ] No se generaron tipos ni artefactos de cliente y no se afirma aceptación UI propia.
- [ ] Si necesitás Mongo, validá URI/hosts/base efectiva antes de conectar/índices, en instancia efímera dedicada.

## Entrega y traspaso

Informá rutas y artefactos backend, operaciones soportadas versus propuestas, decisiones abiertas y pruebas realizadas/pendientes. Entregá a N8 matriz de compatibilidad y recuperación; a N9, diagnóstico del comando incierto. No declares despliegue, integración externa ni compatibilidad no probada.
