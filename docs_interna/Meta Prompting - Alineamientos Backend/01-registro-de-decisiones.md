# Registro de decisiones aprobadas

Fecha de aprobación: 5 de noviembre de 2026, en la ejecución de N0 con el usuario.
Evidencia: respuestas explícitas del usuario a las preguntas de N0 tras la caracterización read-only verificada (sin deriva respecto de la auditoría 06).

Este registro es la fuente de verdad de decisiones de producto/diseño para los prompts de esta carpeta. La [guía común](00-guia-de-ejecucion.md) describe qué decide cada ID; aquí consta su estado. Ninguna etapa puede reabrir una decisión aprobada sin nueva autorización del usuario.

## Decisiones aprobadas

| ID | Estado | Decisión aprobada |
|---|---|---|
| D01 | APROBADA | Nueva familia versionada `/api/narrative/v3` para el protocolo de comandos/recibos. Endpoints actuales quedan intactos para runs legacy y se bloquean sobre runs nuevas. |
| D02 | APROBADA | Resultado/continuación persistidos y recuperables al recargar; `CONTINUAR_RESULTADO` explícito, sin repetir efectos ni azar. Se mantiene `completed/game_over`. |
| D03 | APROBADA | Credencial invitada firmada/verificable emitida por backend para aislar runs; JWT inválido se rechaza (401), no degrada a invitado. Economía invitada sigue local; mismo origen por proxy, CORS solo si se necesita. |
| D04 | APROBADA (solo V2) | Duplicados iniciales rechazados; copias posteriores como instancias con pasivos por copia. Recursos/personajes desconocidos rechazados al validar contenido. Redondeo del servidor documentado y testeado. |
| D05 | APROBADA | Solo se corrige el 0%: una misma función de pesos para proyección y sorteo; lo mostrado como 0% nunca se sortea. Pools V2 por universo y conversación incidental 40% se conservan. |
| D07 | APROBADA | Reinicio remoto explícito con nueva generación/ID de run y `expectedVersion`, sin nueva recompensa del mismo slot. Limpieza de demo es operación separada. |
| D08 | APROBADA | Transacciones Mongo si el entorno las soporta (verificación aislada); si no, documento único con CAS previa medición de tamaño/retención. Sin cambios de infraestructura por defecto. |
| D09 | APROBADA | Cada run queda atada a una revisión inmutable de todo su contenido; publicar en admin crea revisión nueva y las runs activas conservan la anterior. Revisiones referenciadas no se borran; contenido inválido existente se reporta, no se borra. |

## Decisión de alcance: retiro de V1

El usuario decidió que **el motor V1 y sus rutas se retiran**:

- El protocolo nuevo `/v3` se construye **únicamente sobre el motor de grafos V2**.
- El contenido V1 de **eventos y conversaciones se convierte a grafos si falta pasarlo**; si ya está completo en V2, no se hace conversión adicional. Inventario de cobertura pendiente (N3/N5).
- **Cartas, objetos, personajes y demás catálogos compartidos no cambian**: ya los usa V2 y siguen siendo los mismos.
- V1 queda congelado como legacy mientras tenga runs/clientes; no se invierte en llevarlo al protocolo nuevo. N5 se reenfoca de «migrar flujo V1» a «inicio/adquisición común + conversión condicional de contenido a grafos».

## Decisiones pendientes

| ID | Estado | Impacto |
|---|---|---|
| D06 | DIFERIDA a pedido del usuario | Política de dominio por edad (atenuación 50%, selección automática, preferencias de conversación). N0 usa fixtures no adaptadas; bloquea N5 para runs adaptadas nuevas. La adaptación visual se conserva. |
| D10 | PENDIENTE (N8) | Cohorte, migración de runs activos, reversión y retiro de contratos legacy. |
| D11 | PENDIENTE (N9) | Señales observables, retención, acceso y umbrales. |

## Nota de compatibilidad con el plan original

La auditoría 06 proponía migrar V1 y V2 al protocolo nuevo y convertir V1 solo como contrato legacy de finalización. La decisión de retiro de V1 prevalece sobre ese plan: las etapas N5/N6/N8 deben leerse con el alcance actualizado, y el contrato `/v3` no necesita adaptadores de comandos V1 (`DECIDIR_EVENTO`/`RESPONDER_CONVERSACION` planos) salvo para la conversión de contenido.
