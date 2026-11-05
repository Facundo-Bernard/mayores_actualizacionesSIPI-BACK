# N1 — Integridad de las transiciones e identidad

## Rol y misión

Actuá como responsable de persistencia y fronteras de acceso del narrativo. Al ejecutarse esta etapa, eliminar carreras de creación, escrituras parciales de grafos y lecturas incoherentes, conservando la lógica de los motores. Los cambios de identidad y reinicio solo se implementan tras su aprobación específica.

Leer la [guía común](00-guia-de-ejecucion.md), [N0](N0-bases-contrato-y-caracterizacion.md) y las evidencias E02–E04/E10–E12 y etapa N1 de la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md).

## Contexto que debe revalidarse

En el corte auditado, `crear_run` usaba `replace_one(upsert=True)` después de consultar ausencia y reiniciaba la versión a cero. El OCC de `persistir_run` protege una escritura, no toda una transición con varias escrituras. `iniciar_grafo_en_partida` persistía fase/puntero antes de que su llamador guardase recursos y demás efectos. La proyección general volvía a leer el run para obtener el grafo.

La dependencia de identidad convertía JWT inválido en usuario 0. Había soporte opcional de `X-Guest-Id`, no transportado por el frontend inspeccionado; eso no constituye por sí mismo una identidad remota verificable. No afirmar explotación en producción: aquí se corrigen invariantes demostradas con pruebas aisladas.

Fuentes B:

- `app/features/narrative/game/run_repository.py`: `crear_run`, `_filtro_version`, `persistir_run`.
- `app/features/narrative/game/setup_service.py`: `iniciar_partida`, `reiniciar_partida`.
- `app/features/narrative/game/motor_v2/turn_service.py` y `graph_engine.py`: inicio, avance, especiales y conversaciones encadenadas.
- `app/features/narrative/game/turn_state.py`: proyección; `game/router.py`, `game/identity.py`: propietario efectivo.
- `app/core/security.py`, `app/core/dependencies.py`, `app/main.py`: JWT, controles de cuenta/servicio, CORS y routers; no asumir que un middleware global completa la autorización.

El transporte de clientes es evidencia externa de compatibilidad; N1 no modifica el frontend.

## Dependencias y frontera de alcance

Exigir evidencia de aislamiento de N0 y contrato de acceso/reinicio antes de modificarlos. La reproducción de carreras y la extracción de cálculos en memoria pueden prepararse sin decidir transporte invitado.

N1 no introduce todavía recibos generales ni demuestra recuperación de respuesta perdida: eso pertenece a N2. No llamar idempotente a una creación exclusiva sin resolver qué devuelve una segunda intención. No refactorizar todos los repositorios ni imponer otra arquitectura al proyecto.

## Paradas obligatorias

- **D03:** antes de editar autorización, CORS, emisión de identidad o cliente, presentar alternativas de identidad invitada verificable y preguntar cuál se aprueba. Precisar JWT inválido, expirado, cuenta inactiva, servicio no permitido y ausencia de credencial. No eliminar invitados ni inventar un usuario/saldo servidor para resolver propiedad.
- **D07:** antes de cambiar reinicio o IDs, preguntar si se permite reinicio remoto y qué ocurre con runs existentes. Nueva generación no puede habilitar recompensa nueva del mismo slot. No borrar runs como migración implícita.
- **D01:** si el arreglo requiere cambiar respuesta/status público de creación concurrente, detener ese cambio hasta acordar la compatibilidad con consumidores actuales.
- Si una extracción altera orden de reglas o resultado visible, consultar D04/D05 o separar esa modificación. No aprovechar la atomicidad para rebalancear el juego.

## Secuencia de implementación

1. Revalidar llamadas reales y dibujar, en el traspaso, las escrituras de cada transición. Cubrir inicio de partida, carta que inicia grafo, terminal que encadena especial/conversación y derrota. Detectar todos los llamadores antes de quitar un commit interno.
2. Reproducir doble inicio con barrera de concurrencia en DB efímera: dos lecturas de ausencia seguidas de creación. Implementar inserción exclusiva y resolución de duplicado según contrato, sin resetear ni sobrescribir el run ganador.
3. Convertir helpers de preparación de grafos en operaciones sobre el estado en memoria. El coordinador confirma juntos fase, puntero, recursos, inventario, tags, afinidad e historial necesarios. Evitar una rama terminal que mantenga una escritura oculta.
4. Mantener el filtro OCC y conflicto observable. Si se pierde la carrera, no responder consecuencias de la copia no confirmada ni liquidar sus recompensas. La prueba debe mostrar una única transición ganadora.
5. Construir proyecciones desde el mismo run leído, pasando estado a los adaptadores en lugar de volver a consultar por usuario/fecha. Las lecturas de contenido deben respetar el diseño versionado de N3 cuando esté disponible; no simular que ya existe.
6. Tras D03, integrar identidad y propiedad con las dependencias actuales. Probar el transporte elegido en mismo origen y, solo si fue aprobado, CORS cruzado. No aceptar propietario declarado en payload como autoridad.
7. Tras D07, proteger reinicio con versión/generación y política de creación aprobada; impedir que una respuesta del run anterior altere el nuevo. Respetar el slot económico existente.

## Pruebas y aceptación

- [ ] Dos inicios simultáneos no sobrescriben estado ni devuelven resultados contradictorios como ganadores.
- [ ] Fallo inyectado antes de confirmación deja el run anterior completo; después, se observa el nuevo completo.
- [ ] Inicio y encadenamiento V2 no exponen fase nueva con recursos antiguos.
- [ ] Conflicto OCC no produce efectos ni recompensas externos de la resolución perdedora.
- [ ] GET usa una versión coherente de run aunque haya una escritura concurrente.
- [ ] Según D03: invitado A no accede a B; JWT inválido no se transforma silenciosamente en una sesión compartida; usuario/servicio se validan.
- [ ] Según D07: reinicio concurrente y respuesta tardía no restauran una generación anterior ni habilitan otro premio.
- [ ] Regresiones V1, V2, finalización, SSO y consumidores legacy cubiertas sin cambiar contratos no aprobados.

Usar Mongo aislado real para carreras, no únicamente un diccionario mock. Verificar el transporte mediante pruebas HTTP y contrato; la validación UI pertenece al responsable externo. Si falta aprobación de identidad/reinicio, informar N1 parcial: la extracción interna puede entregarse separada, pero no cerrar toda la etapa.

## Entrega y traspaso

Listar los puntos de escritura eliminados, el coordinador que queda, decisiones aplicadas, contratos preservados y pruebas ejecutadas. Entregar a N2 una frontera de mutación única y explicitar que OCC por sí solo aún no ofrece recibos ni control de versión vista por el cliente. No commitear, publicar ni iniciar N2 automáticamente.
