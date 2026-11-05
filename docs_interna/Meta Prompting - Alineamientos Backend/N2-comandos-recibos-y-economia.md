# N2 — Comandos idempotentes, recibos y cierre económico

## Rol y misión

Actuá como responsable del protocolo durable narrativo. Implementar, cuando esta etapa sea solicitada, una frontera que confirme estado, respuesta recuperable y obligación económica como una sola unidad lógica. Reutilizar OCC y ledger actuales; no confundir idempotencia de puntos con idempotencia de una decisión narrativa.

Leer la [guía común](00-guia-de-ejecucion.md), entregas de [N0](N0-bases-contrato-y-caracterizacion.md)/[N1](N1-integridad-e-identidad.md) y secciones 7/N2 de la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md). N2 requiere sus contratos aprobados y pruebas de persistencia, no solo estos documentos.

## Contexto y fuentes

El run ya tiene OCC interno, pero los requests legacy no expresan `expectedVersion` ni `commandId`. El cierre de run precede a intento/ledger; una caída antes del asiento deja una obligación que el reconciliador de asientos no puede descubrir. `puntos_ganados` legacy expresa un delta por request: reproducir un recibo con puntos positivos necesita deduplicación distinta en el cliente invitado.

Leer en B:

- `app/features/narrative/game/run_repository.py` y `app/features/narrative/schemas/game_schemas.py`; contrastar los DTOs actuales con la entrega aprobada de N0.
- `app/features/narrative/game/endings_service.py`: `sincronizar_intento_usuario` y sus llamadores de cierre.
- `app/shared/ledger.py`, `app/features/user_attempts/`, `app/main.py`: claves de negocio y reconciliación existente.
- `app/core/database.py`, configuración y fixtures aisladas aprobadas en N0.

Localizar implementaciones actuales antes de añadir archivos. No agregar una capa genérica para todos los juegos.

## Paradas obligatorias

- **D08 — almacenamiento:** antes de persistir recibos, presentar capacidades comprobadas de Mongo y elegir con el usuario transacción o documento único. No cambiar topología. Si no hay transacciones, demostrar límites BSON de 16 MB, crecimiento, retención y recuperación del diseño alternativo; no aceptar «run ahora, recibo después».
- **D08 — semántica:** aprobar hash canónico, alcance de clave, retención, tratamiento del commit incierto, RNG y recibo económico. Preguntar cómo se consulta una liquidación posterior sin alterar la respuesta de dominio ya confirmada. No podar recibos y luego volver a ejecutar la misma clave.
- **D01/D02:** antes de publicar DTOs/rutas, confirmar protocolo, códigos de error y relación snapshot/resultado pendiente. No convertir campos opcionales legacy en una falsa garantía del contrato nuevo.
- **D03/D07:** ante dudas de propietario, slot o generación, detener ese camino. Un reinicio no crea otro derecho a recompensa.
- Antes de índices o reconciliación en DB compartida, solicitar autorización específica. N2 se valida primero en una base efímera.

## Secuencia de implementación

1. Verificar en entorno aislado soporte de sesiones/transacciones, write concern y unicidad requerida. Registrar evidencia sin URI secreta. Diseñar índice por principal/run/comando y ámbito de creación por principal/slot, incluyendo generación según contrato aprobado.
2. Definir payload discriminado y canonicalización del tipo, payload y versión esperada. La identidad se deriva de credenciales; nunca de un campo controlado por el cliente. Crear pruebas de equivalencia y reutilización de clave con contenido diferente.
3. Implementar flujo: autorizar propietario; buscar recibo; si existe y el hash coincide, devolver respuesta confirmada; si no coincide, rechazar. **Solo si no existe recibo**, comprobar versión, fase, reglas y resolver. Una versión vieja no invalida la recuperación del recibo original.
4. Inyectar reloj, RNG y catálogo como dependencias acotadas. Confirmar por CAS y estrategia atómica aprobada run, recibo y consecuencias/resultado. Las resoluciones perdedoras no se publican. Un recibo confirmado nunca se vuelve a sortear; ante resultado de commit incierto, reconciliar con la misma clave antes de intentar una nueva intención.
5. Diferenciar resultado desconocido de fallo definitivamente no confirmado. «Recibo no encontrado» no prueba que otro request aún en vuelo no vaya a confirmar. Los reintentos conservan clave y payload; no generan una clave nueva automáticamente.
6. Persistir obligación durable de sincronizar intento y recompensa junto al cierre. Reutilizar claves/idempotencia del ledger para entrega y reintento. El reconciliador descubre obligaciones sin asiento y también resuelve confirmación del crédito seguida de caída antes de marcar entrega.
7. Exponer `rewardId` y estado económico según D08. En invitados, la recompensa sigue siendo local y debe acreditarse una sola vez por ese ID; no implementar saldo invitado servidor. Mantener separado el contrato legacy de delta por request.
8. Integrar lectura autorizada de recibos/snapshot y guardar la frontera para el piloto N4. No habilitar a usuarios una familia de comandos parcialmente implementada ni permitir mutaciones legacy sobre runs nuevos.

## Pruebas y aceptación

- [ ] Mismo comando simultáneo: una confirmación, una versión nueva y respuesta durable equivalente.
- [ ] Dos `commandId` distintos crean como máximo una partida activa para el mismo principal/slot; la exclusividad de creación no depende de compartir clave de recibo.
- [ ] Misma clave/payload cambiado: rechazo sin mutación. Clave distinta/versión vieja: conflicto sin resolución publicada.
- [ ] Repetición confirmada se recupera aunque el run haya avanzado; no regresa estado ni reevalúa RNG.
- [ ] Fallo antes del commit, pérdida de respuesta después, reinicio de proceso y commit incierto tienen recuperación comprobada.
- [ ] No existe run nuevo sin recibo correspondiente ni recibo de una mutación no confirmada.
- [ ] Cierre sin asiento se repara; crédito aplicado antes de caída no vuelve a acreditarse.
- [ ] Propiedad, generación y slot se verifican para lectura y escritura; invitados no comparten identidad.
- [ ] Concurrencia real Mongo y límites de almacenamiento probados; mocks no sustituyen esa evidencia.

## Entrega y traspaso

Entregar esquema aprobado, índices ensayados, orden de validación, política de recuperación/retención, evidencias de fallos y contrato de recompensa. Informar limitaciones del entorno sin declarar atomicidad productiva no medida. N3 coordina las referencias de contenido; N4 consume esta frontera. No desplegar ni ejecutar migraciones al finalizar.
