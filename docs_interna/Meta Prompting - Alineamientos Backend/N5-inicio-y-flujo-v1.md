# N5 — Inicio, adquisición y conversión de contenido a V2

> Alcance actualizado el 2026-11-05 por decisión del usuario: **V1 se retira**. El protocolo `/v3` es solo V2; esta etapa ya no migra el flujo V1 al protocolo nuevo. Ver [registro de decisiones](01-registro-de-decisiones.md).

## Rol y misión

Actuá como implementador backend cuando el usuario invoque esta etapa. Completá inicio, corte, adquisición de cartas y modelo de resultado/continuación sobre las garantías de N4, y convertí a grafos el contenido V1 de eventos/conversaciones **solo donde falte cobertura V2**. Los catálogos compartidos (cartas, objetos, personajes) no cambian: ya los usa V2.

Leé completas la [guía común](00-guia-de-ejecucion.md), el [registro de decisiones](01-registro-de-decisiones.md) y la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) como contexto histórico. Si falta la guía o el registro, detené implementación dependiente.

## Lectura técnica obligatoria

Localizá en B por símbolos, revalidando líneas:

- B: `app/features/narrative/game/setup_service.py`: `iniciar_partida`, `reiniciar_partida`; `game/motor_v1/turn_service.py`: `elegir_carta_mes` (lógica de adquisición a reutilizar, no el motor plano).
- B: `app/features/narrative/engine/rule_engine.py`: `despachar_efectos`; `game/motor_v2/turn_service.py` y `graph_engine.py`: cómo V2 consume cartas/personajes hoy.
- B: catálogos V1 (`COLL_EVENTS`, `COLL_CONVERSATIONS`, resultados) versus colecciones de grafos V2: definir equivalencias de contenido antes de convertir.
- B: `app/features/narrative/schemas/v3_contract_schemas.py` y `v3_openapi.py`: contrato objetivo de inicio, snapshot y resultado.

## Contexto verificado versus hipótesis

Al 2026-11-05 la selección valida longitud y pertenencia a oferta, no unicidad; `$in` colapsa duplicados. V2 ya consume los mismos catálogos de cartas/personajes. No se conoce todavía la cobertura real de eventos/conversaciones V1 en grafos V2: **inventariar antes de convertir**, sin asumir que falta ni que sobra contenido.

El usuario identifica producción con `JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, rama `main`; la comparación conocida con `feature/refactor-backend` difiere solo en build admin. Esto no certifica despliegue. Revisá HEAD/diffs actuales sin sincronizar. `/api/narrative/v3` está aprobado como superficie; sus DTOs concretos se diseñan en esta etapa dentro de D01/D02.

## Dependencias y evidencia requerida

Exigí entrega verificable de N4 y sus bases N1/N2/N3: creación exclusiva, identidad aislada, CAS, recibos durables, RNG recuperable, contenido fijado por revisión y proyecciones backend reanudables. Pedí rutas/símbolos actuales y resultados reproducibles, no fechas o SHAs como garantía. D03/D08 ya están aprobadas: aplicarlas, no reabrirlas. El modelo de resultado D02 implementado aquí es dependencia contractual de N6.

## Alcance y exclusiones

Conservá tres personajes, tres cartas iniciales, una adquisición mensual y doce meses sin turno 13. El flujo nuevo es exclusivamente V2. **No migres `DECIDIR_EVENTO` ni `RESPONDER_CONVERSACION` planos al protocolo nuevo**: V1 legacy queda congelado y sus rutas se mantienen solo para runs/clientes existentes hasta el retiro de N8.

Excluí: nuevo motor, nuevo ledger, economía guest servidor, cambios de balance no aprobados, rediseño admin y conversión masiva de contenido sin inventario previo. No sobrescribas cambios ajenos ni hagas commit, push, sincronización, infraestructura, permisos o DB compartida sin autorización. Preservá B:`app/static/admin/test-narrativo.html` en cualquier build admin autorizado.

## Paradas obligatorias y preguntas específicas

Las decisiones aprobadas se aplican; solo quedan paradas las pendientes o discrepancias nuevas:

- **Antes del paso 2, D01/D02 (aplicación):** verificá que el contrato aprobado cubra estados, resultado pendiente y continuación. Si aparece un caso no previsto (por ejemplo, resultado previo al final), proponé extensión y consultá antes de implementarla.
- **Antes del paso 3, conversión de contenido:** presentá el inventario V1→V2 con brechas concretas y preguntá qué conversiones se autorizan. Eventos V1 con condiciones/resultados que no tengan equivalente en grafos requieren mapping aprobado; no inventes nodos ni probabilidades.
- **D06 — DIFERIDA:** no implementes atenuación del 50%, selección automática ni preferencias de conversación en el servidor. Las runs nuevas del protocolo se crean sin política adaptada; si el usuario quiere habilitar runs adaptadas, esta etapa se detiene en ese punto hasta su decisión. Adaptación visual se conserva.
- **Antes del paso 5, D05 aplicada:** la corrección del 0% usa una sola función de pesos en V2; pools y 40% incidental se conservan. Cualquier otra diferencia de azar encontrada se reporta, no se corrige por iniciativa propia.
- **D07 aplicada:** reinicio remoto con nueva generación, `expectedVersion` y sin nueva recompensa del slot; limpieza de demo separada.

Si falta aprobación o dependencia, avanzá solo inspección/pruebas aisladas independientes. No implementes alternativas provisionales ni rebajes garantías.

## Secuencia numerada

1. Inspeccioná cambios concurrentes y caracterización vigente; vinculá cada transición común con fase, guarda, efecto y prueba.
2. Adoptá contrato aprobado y modelo común de resultado: ID estable, texto incluso neutral, consecuencias y continuación durable; GET no ejecuta negocio.
3. Inventariá contenido V1 de eventos/conversaciones contra cobertura V2. Tras autorización, convertí solo las brechas, con validación de grafos, revisión de contenido nueva y pruebas de equivalencia de efectos. Los desafíos/universos pasan a motor V2 solo cuando su contenido queda cubierto.
4. Mantené corte/cartas provisionales hasta confirmar inicio. Validá oferta, selección y unicidad (D04); ejecutá adquisición una vez con instancias explícitas y reemplazá corte, inventario y tags completos desde snapshot.
5. Migrá la elección de carta mensual al coordinador común: adquisición, colapso y preparación del evento V2 en una sola confirmación. Afinidad y recursos se sustituyen con respuesta autoritativa, preservando cero.
6. Implementá `CONTINUAR_RESULTADO` idempotente sin resorteo/reaplicación. Integrá reinicio remoto según D07 y cierre económico común.
7. Probá y entregá el contrato de resultado a N6/N7 antes de retirar caminos dependientes.

## Pruebas y criterios de aceptación

- [ ] Inicio concurrente, repetición idéntica, payload diferente y versión vieja no duplican adquisición ni mutaciones.
- [ ] Duplicados iniciales rechazados; copias posteriores aplican pasivos por instancia según D04.
- [ ] Resultado pendiente bloquea avance; continuar dos veces no repite efectos; afinidad cero se conserva.
- [ ] Conversión autorizada cubre las brechas inventariadas con grafos válidos y efectos equivalentes; no hay contenido V1 convertido dos veces.
- [ ] Recorrido V2 completo de doce meses con cuenta/invitado en base aislada; final no se calcula localmente; recompensa guest se deduplica por `rewardId` sin nueva acreditación del slot.
- [ ] Runs nuevas no exponen política adaptada de dominio mientras D06 siga diferida.
- [ ] Antes de conectar Mongo/crear índices, validá hosts y base efectiva de URI; `MONGODB_DB_NAME` solo no basta. Usá base efímera dedicada.
- [ ] La aceptación backend usa pruebas HTTP/DB aisladas; la integración UI queda como evidencia externa pendiente y no se certifica mediante mocks.

## Entrega y traspaso

Informá archivos, decisiones aplicadas, cobertura de conversión, pruebas ejecutadas/no ejecutadas y bloqueos (incluido D06 si aplica). Entregá a N6 el modelo de resultado con fixtures y a N7 las proyecciones V2. No declares implementación desplegada ni etapas ajenas terminadas.
