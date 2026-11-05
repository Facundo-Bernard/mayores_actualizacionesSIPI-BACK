# Auditoría de arquitectura recibida y plan integral narrativo

Fecha: 5 de noviembre de 2026.
Estado: análisis y propuesta de implementación; no autoriza por sí mismo cambios de producto, despliegues ni modificación de infraestructura.

## 1. Conclusión ejecutiva

**El análisis recibido no tomó como base nuestro backend de juegos refactorizado.** Tomó `Facundo-Bernard/mayores_actualizacionesSIPI-BACK`, rama `main`, commit `33cdf8f`, correspondiente al backend educativo. Su diagnóstico de rutas ausentes es válido para ese corte, pero no describe nuestra rama `feature/refactor-backend@7b86563`.

**La propuesta de evolución sí tiene valor:** comandos idempotentes, versión esperada por el cliente, consecuencias confirmadas, contenido fijado por partida y separación entre dominio y presentación. Nuestro backend ya calcula y persiste las reglas, tiene dos motores, guardas, OCC y ledger; falta completar garantías y alinear al cliente. No hay que reconstruir esas capacidades desde cero.

La prioridad no es cambiar nombres de fases ni introducir un framework. Es impedir escrituras parciales, resolver identidad y creación concurrente, conservar resultados reanudables y evitar que Redux o una animación vuelvan a ejecutar negocio.

## 2. Procedencia comprobada y límites de la revisión

### 2.1 Qué se tomó originalmente

La [especificación recibida:23–30](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/arquitectura/motor-acciones-y-maquina-de-estados.md#L23) identifica expresamente:

- Frontend `MontiNahuel/juegos-mayores-actualizaciones`, referencia `0f12188`.
- Backend `Facundo-Bernard/mayores_actualizacionesSIPI-BACK`, referencia `33cdf8f`.
- La necesidad de identificar el backend que realmente atiende la web antes de implementar.

El [HTML:244–260](file:///C:/Users/nmonti/Desktop/proyectos/frontend/arquitectura-cognijuegos.html#L244) fija propietario, rama, commit y enlaces de fuentes. Declara lectura estática, sin iniciar backend, MongoDB ni autenticador. El propio [HTML:68–73](file:///C:/Users/nmonti/Desktop/proyectos/frontend/arquitectura-cognijuegos.html#L68) detecta otro checkout de juegos en el workflow, pero no verifica su topología.

Las [capturas:3–16](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/imagenes/arquitectura/README.md#L3) son de la web publicada, como invitado; las de narrativa son del modo de prueba. **Una captura de producción no identifica qué backend se analizó ni acredita integración remota.**

Git confirma que la guía entró con `a10bb7f` y fue ampliada con `d44747a`. En el clon completo actual, `33cdf8f` y nuestro HEAD no tienen ancestro común detectable: no corresponde describirlo simplemente como «nuestra rama unas versiones atrás».

### 2.2 Qué tenemos ahora

| Referencia local verificada | Estado |
|---|---|
| Frontend `feature/juego-narrativo` | `b54ea41`, con la documentación de `origin/main@d44747a` integrada. |
| Backend `feature/refactor-backend` | `7b86563`. |
| Backend `origin/main` | `33cdf8f`: justamente el corte educativo usado por la guía. |
| Backend `prod-games/main` y `main` local | `9cb670c`, remoto `JNicolasFernandezG/juegos-mayores-actualizaciones-back`. |
| Diferencia `prod-games/main..7b86563` | Solo compilación del panel admin; sin diferencia en lógica de aplicación, pruebas o documentación interna. |

Las referencias remotas son las disponibles localmente; esta auditoría no volvió a hacer fetch ni inspeccionó servidores productivos. Tampoco atribuye a producción el SHA del checkout local.

El backend local en `localhost:8090` respondió OpenAPI con 98 rutas, incluyendo avance por nodos, estado narrativo, economía, login administrativo y SSO. Esto confirma disponibilidad de contratos en ese proceso; no demuestra por sí solo un recorrido completo ni el SHA desplegado. El título genérico y la versión `2.0.0` de OpenAPI no identifican una compilación.

**Respuesta a la pregunta central:** no hay evidencia de que la auditoría recibida haya contrastado nuestra rama refactorizada ni `prod-games/main`. Sus referencias y sus conclusiones sobre capacidades ausentes muestran que utilizó otra base. Sí dejó una advertencia correcta para resolver esa diferencia antes de implementar.

### 2.3 Alcance realizado

- Lectura de los 18 capítulos del HTML, incluido su JavaScript embebido.
- Lectura de toda la especificación Markdown y de los tres módulos interactivos y sus pruebas.
- Contraste de servicios, motores, DTOs, identidad, persistencia, frontend narrativo, validadores y documentación previa del refactor.
- Revisión contextual de rutas, seguridad JWT, intentos, hosting del panel y configuración de desarrollo/despliegue.
- No se reabrió el ZIP GDD original: se auditó cómo la propuesta declara utilizarlo.
- No se auditó una base productiva ni se certificó la totalidad de clásicos, autenticador o infraestructura. Esas áreas se revisaron para corregir el diagnóstico documental y delimitar el alcance, no para proponer otra reescritura.

## 3. Auditoría de la documentación de punta a punta

| Bloque | Evaluación y corrección necesaria |
|---|---|
| HTML 1–4: visión, mapa, flujo e integración | Buena distinción entre código, rutas e integración. La matriz pertenece al backend educativo y debe publicarse como revisión histórica, no como estado actual de CogniJuegos. |
| HTML 5: frontend | La estructura general sigue siendo útil. El panel ya no se monta mediante `NarrativoAdminPage`: los aliases redirigen a `/admin`. |
| HTML 6: clásicos | Sirve como descripción del cliente inspeccionado. Las frases «no hay economía/pistas en backend» quedan invalidadas para nuestra rama. No autoriza cambiar scoring ni vidas. |
| HTML 7: narrativa | Buen inventario de divergencias locales/remotas. Shooter es una reserva «Próximamente», no un requerimiento implementable con reglas definidas. |
| HTML 8 y Markdown | Propuesta coherente de autoridad, Command, FSM, ECA y persistencia. Especificación de destino, no descripción de una migración realizada. Reutilizar motores y ledger existentes. |
| HTML 9: estado y economía | Útil separación entre Redux, Context, almacenamiento y servidor. No extrapolar el guardado local de invitados clásicos a la identidad de runs narrativas remotas. |
| HTML 10: administración | Desactualizado frente al shell independiente servido por backend. Validación/publicación de contenido sí entra en esta migración; rediseñar el editor de grafos no. |
| HTML 11–13: backend, datos y API | Rehacer contra el backend de juegos. Existen routers narrativos, grafos, economía, SSO y los campos de calificación/tiempo/recompensas. El índice diario de intentos no prueba ausencia de slots por dificultad: existe `by_difficulty`. |
| HTML 14–15: infraestructura y arranque | Vite versionado usa 5174; nuestro backend/Compose usa 8087 como default, no 8082. La instancia local inspeccionada está en 8090. La advertencia de Capacitor con servidor HTTP local sigue siendo pertinente. |
| HTML 16–17: cambios y glosario | Conservar método de seguimiento de contratos; corregir ejercicios que parten de rutas faltantes en el backend actual. |
| HTML 18: fuentes | Es la evidencia decisiva del corte equivocado. Mantener esa procedencia y agregar una nueva revisión, no cambiar solo los hashes dejando el diagnóstico anterior. |

### 3.1 Calidad y límites de los laboratorios

Los módulos [juegos-narrativos.js](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/componentes/juegos-narrativos.js), [coordinacion-narrativa.js](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/componentes/coordinacion-narrativa.js) y [patron-narrativo.js](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/componentes/patron-narrativo.js) son material didáctico, no una implementación para trasladar literalmente.

El laboratorio separa correctamente envío, confirmación, recepción y animación. Sin embargo:

- Consulta recibos solo por `commandId`, sin comparar el payload: `patron-narrativo.js:45–49`.
- No libera `pending` al finalizar; una segunda intención requiere recargar el modelo: líneas 39–41 y 80–110.
- El snapshot no conserva el contenido de resultado; recargar pierde el paquete de presentación: líneas 35–37 y 107–110.
- Sus diez tests no prueban autenticación, base real, múltiples comandos de una partida ni transacciones.
- La descripción de preferencias de conversación mezcla el 50%/75% local con el envío real: el cliente solo manda esa preferencia en modo adaptado y el DTO backend actual no la declara. No convertir esa descripción en nueva probabilidad remota.

La [especificación:130–148](file:///C:/Users/nmonti/Desktop/proyectos/frontend/docs/arquitectura/motor-acciones-y-maquina-de-estados.md#L130) llama al ejemplo «respuesta de una carta mensual», pero el comando es `AVANZAR_MES` y la fase resultante es draft: interpretarlo como pasivo mensual de una carta ya poseída, no como adquisición de una carta nueva.

## 4. Evidencia principal de implementación actual

Las referencias siguientes permiten revisar los hallazgos sin confundir documentos históricos con código ejecutable.

| ID | Fuente y responsabilidad |
|---|---|
| E01 | [app/main.py:114–176](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/main.py#L114): OpenAPI y routers actuales. |
| E02 | [game/router.py:77–99](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/router.py#L77) e [identity.py:21–71](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/identity.py#L21): identidad narrativa. |
| E03 | [run_repository.py:22–63](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/run_repository.py#L22): creación y OCC. |
| E04 | [setup_service.py:93–219](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/setup_service.py#L93): ofertas, adquisición, motor y reinicio. |
| E05 | [game_schemas.py:89–242](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/schemas/game_schemas.py#L89): contrato actual. |
| E06 | [transition_service.py:61–168](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/transition_service.py#L61): balance, mes 12 y pasivos. |
| E07 | [rule_engine.py:15–159](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/engine/rule_engine.py#L15): ECA y redondeo. |
| E08 | [event_director.py:108–173](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/engine/event_director.py#L108): probabilidades mostradas y sorteo. |
| E09 | [motor_v1/turn_service.py:161](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/motor_v1/turn_service.py#L161): decisiones y condiciones V1. |
| E10 | [motor_v2/turn_service.py:26–43](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/motor_v2/turn_service.py#L26) y [graph_engine.py:237–245](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/motor_v2/graph_engine.py#L237): inicio de grafo con escrituras separadas. |
| E11 | [graph_engine.py:465–549](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/motor_v2/graph_engine.py#L465): terminales, historial y encadenamiento. |
| E12 | [turn_state.py:28–74](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/turn_state.py#L28): reconstrucción de estado. |
| E13 | [endings_service.py:130–234](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/endings_service.py#L130) y [shared/ledger.py:57](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/shared/ledger.py#L57): cierre y acreditación. |
| E14 | [admin/router.py:435](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/admin/router.py#L435) y [validation/graph_validator.py](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/validation/graph_validator.py): validación V2 existente. |
| E15 | [admin/crud_service.py:51](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/admin/crud_service.py#L51) y [universe_resources.py:8](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/game/universe_resources.py#L8): catálogo vivo y caché. |
| E16 | [KingsCourt.tsx:154–377](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/VISTAS/JUEGOS/NARRATIVO/KingsCourt.tsx#L154): orquestación, avance y adaptación. |
| E17 | [narrativoSelectionSlice.ts:53–269](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/store/narrativoSelectionSlice.ts#L53): dominio local e hidratación parcial. |
| E18 | [narrativeService.ts:261–402](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/VISTAS/JUEGOS/NARRATIVO/narrativeService.ts#L261): transporte, fallback y grafos. |
| E19 | [adaptacionEdad.ts:3–53](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/config/adaptacionEdad.ts#L3): adaptación visual y pérdidas locales. |
| E20 | [routes.tsx:44–75](file:///C:/Users/nmonti/Desktop/proyectos/frontend/src/VISTAS/routes.tsx#L44): panel independiente. |
| E21 | [user_attempts/schemas.py:8–47](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/user_attempts/schemas.py#L8) y [security.py:57–75](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/core/security.py#L57): campos actuales y validación de expiración. |
| E22 | [docker-compose.yml:17–73](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/docker-compose.yml#L17), [Caddyfile:41–51](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/Caddyfile#L41), [vite.config.ts:27–48](file:///C:/Users/nmonti/Desktop/proyectos/frontend/vite.config.ts#L27) y [capacitor.config.ts:8–11](file:///C:/Users/nmonti/Desktop/proyectos/frontend/capacitor.config.ts#L8): topología declarada. |

## 5. Matriz de capacidades: qué existe y qué falta

| Requisito recibido | Estado actual | Trabajo real |
|---|---|---|
| Backend autoritativo | Existe para las mutaciones remotas; el cliente también calcula. | Eliminar segunda autoridad en partidas remotas, no crear otro motor. E04/E07/E16/E17. |
| Grafos V2 | Implementados, con opciones condicionadas y desenlaces. | Conservarlos y resolver atomicidad/proyección/reanudación. E10/E11. |
| Máquina de dominio | Fases y guardas distribuidas. | Inventario exhaustivo de transiciones y contrato común; resultados pendientes explícitos. |
| OCC | Comparación de versión leída y actualización atómica por escritura. | Exponer versión y exigir la que vio el cliente; una confirmación por comando. E03. |
| Idempotencia | Existe en ledger de puntos, no como recibo narrativo general. | Recibos de comandos con hash y respuesta durable. No confundir ambas claves. E13. |
| Snapshot completo | Respuestas parciales y GET con campos opcionales. | Proyección coherente desde una única lectura, inventario/corte/tags, fase y comandos. E05/E12. |
| Consecuencias | Efectos declarados, impactos y resúmenes, no registro uniforme antes/después. | Capturar valores reales al ejecutar, incluyendo clamp, orden, fuente e IDs. E07/E11. |
| Resultado reanudable | IDs/historial parciales; estados de lectura viven también en React. | Persistir resultado y escena siguiente, con reconocimiento idempotente. E11/E12/E16. |
| Contenido/reglas fijados | Motor fijado al run; catálogo releído vivo. | Revisiones inmutables y reglas identificadas. E04/E15. |
| RNG reproducible por comando | `random` global; desenlaces guardados parcialmente. | Azar inyectado y resultado conservado en recibo. E08/E11. |
| ECA validado | Tres acciones ejecutadas; otras capacidades declaradas incompletas. | Catálogo de capacidades real y validación semántica obligatoria. E07/E14. |
| Identidad invitada | Soporte opcional `X-Guest-Id`; cliente auditado no lo manda. | Identidad remota verificable y aislada de la demo; no usar run compartida 0. E02/E18. |
| Finalización/economía | Ledger, intentos y puntos narrativos presentes. | Cerrar ventana entre run final y asiento; recibo de recompensa recuperable. E13. |
| FSM de presentación | Estados/banderas distribuidos, algunos bloqueos de botones. | Control único del comando pendiente y reconciliación. E16/E17. |
| Demo/offline | Fallback local automático y seis meses de simulación. | Modo explícito; nunca sustituir una partida remota por timeout. E18. |

### 5.1 Hallazgos P0: integridad, identidad y recuperación

1. **Creación destructiva en carrera.** `crear_run` hace `replace_one(upsert=True)` y vuelve a versión 0. Dos inicios que leyeron ausencia pueden sobrescribirse. El reinicio reutiliza identidad de documento. Se necesita inserción exclusiva y generación de run inequívoca. E03/E04.
2. **Más de una escritura por transición V2.** Iniciar grafo persiste puntero/fase; después el llamador persiste carta, recursos e historial. Los encadenamientos repiten el patrón. Una caída entre ambas deja un estado parcial aunque cada escritura tenga OCC. E10/E11.
3. **Falta el control de obsolescencia del cliente.** La versión interna no evita que una intención vieja se evalúe contra una lectura nueva compatible por casualidad. Tampoco devuelve la respuesta exacta tras timeout. E03/E05.
4. **Identidad remota incompleta.** JWT inválido termina como invitado; no se aplican aquí todas las comprobaciones de cuenta/servicio del autenticador. Sin identificador invitado se usa 0. El cliente inspeccionado envía token o ningún identificador, por lo que el soporte opcional no resuelve su aislamiento. CORS tampoco declara el header invitado para uso cross-origin. La exposición efectiva depende del despliegue; el problema de contrato está verificado. E01/E02/E18.
5. **Cierre durable incompleto.** Run final, intento y crédito son pasos separados. Si falla antes de crear el asiento, el reconciliador del ledger no lo puede descubrir. Las excepciones se traducen en 0 puntos. No afirmar que el ledger duplica siempre: ya protege la acreditación autenticada. E06/E13.
6. **Dominio adelantado en frontend.** El mes aumenta antes del POST; la conversación altera afinidad antes de confirmar e ignora su respuesta; resultados se aplican entre dos sincronizaciones. Los recursos pueden corregirse después, pero el historial local ya contiene valores transitorios. E16/E17.
7. **Cambio automático de autoridad.** Un timeout tras un POST confirmado puede activar demo local; GET de restauración también permite fallback. No hay conciliación posterior. E18.

### 5.2 Hallazgos P1: semántica y proyección

- **Terminales V2:** el terminal se limpia del grafo activo; si se encadena una escena se devuelve directamente la raíz siguiente. GET no recupera el terminal pendiente. Además, el GET general puede buscar un ID de nodo V2 en resultados V1 y hace una segunda lectura del run para el grafo. E11/E12.
- **Conversación V1:** opción persistida no equivale a resultado pendiente reconstruible. Las condiciones de decisiones no se evalúan; en eventos V1 se exigen solo para opciones secretas. E09.
- **Hidratación parcial:** Redux no sustituye corte, inventario, fase y tags completos; no puede quitar tags mediante la sincronización actual. Una afinidad 0 cae en `|| 50`. La finalización local impone `game_over` incluso si el servidor confirmó victoria. E17.
- **Reglas declaradas no ejecutadas:** ECA implementa modificar recurso, modificar afinidad y otorgar tag. `amortiguar_danio` no tiene handler. Los enums desconocidos sí son rechazados por Pydantic: el problema no es «todo desconocido se acepta», sino capacidades reconocidas pero no implementadas y validación semántica insuficiente. E07.
- **Recursos/personajes ausentes:** ECA puede crearlos; V2 ignora ciertos impactos sobre ausentes. Debe acordarse semántica consistente sin alterar contenido silenciosamente. E07/E11.
- **Probabilidad incoherente:** V1 muestra peso mínimo 0 y sortea con mínimo 0,1; una opción mostrada con 0% puede ocurrir. E08.
- **Orden y duplicados:** consultas `$in` no preservan multiplicidad de cartas ni un orden semántico explícito. Seleccionar tres IDs no garantiza tres elementos distintos. No multiplicar pasivos por copias sin decisión y versión. E04/E06.
- **Adaptación:** el cliente reduce pérdidas al 50% desde 45 años cuando está habilitado y autoelige la primera carta si omite el draft. El backend no recibe una política equivalente. Cambiar edad o restaurar draft puede disparar otro POST desde la UI. E16/E19.

## 6. Decisiones de alcance y diseño recomendadas

El [plan previo:3–8](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/docs_interna/refactor/05-plan-solucion.md#L3) distingue V1 operativo de V2 objetivo. El [relevamiento 02:4–8](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/docs_interna/refactor/02-narrativo-v1-v2.md#L4) es una foto histórica con errata. El [ADR aceptado:24–37](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/docs_interna/refactor/adr/0001-arquitectura-objetivo.md#L24) exige extracción acotada y preservación de contratos.

### Mantener sin abrir otro proyecto

- Python/FastAPI/MongoDB y separación actual por feature.
- V1 operativo y V2 como motor alternativo sujeto a readiness; no declarar V2 oficial por existir la URL `/v2`.
- Tres personajes y tres cartas iniciales; una carta por elección mensual.
- Doce meses: guardar balance, avanzar y aplicar pasivos al entrar al siguiente mes no final. Sin turno 13.
- Recompensas narrativas, incluidos invitados; sin re-acreditar el mismo slot de negocio.
- Economía local del invitado según decisiones previas: una identidad para proteger su run no implica crear un saldo server-side ni un usuario ficticio.
- No rediseñar editor de grafos, clásicos, scoring, imágenes, vidas ni pipelines.
- No microservicios, event sourcing completo, motor TypeScript paralelo o framework FSM obligatorio.

### Resolver antes de activar el nuevo contrato

| Decisión | Recomendación / criterio |
|---|---|
| API vs motor | Versionar el protocolo nuevo, conservando `motor=v1/v2` como eje independiente. «V3 de API» no significa tercer motor. |
| Contrato anterior | No volver obligatorios campos nuevos en endpoints consumidos por clientes actuales. Abrir contrato versionado y bloquear que endpoints viejos muten runs nuevos. Retiro posterior y medido. |
| Estados | Mantener semántica `completed/game_over` o mapearla explícitamente; no renombrar a `failed` de forma implícita. Resultado pendiente puede ser un subestado persistido, sin aplanar grafos. |
| Edad | Conservar adaptación visual. La atenuación de pérdidas y selección automática requieren política de dominio fijada al inicio. No convertir automáticamente el 50% local en balance remoto oficial. Validar con producto esa divergencia antes de habilitar runs adaptados nuevos. |
| Copias de cartas | Rechazar IDs iniciales duplicados. Para copias adquiridas posteriormente, caracterizar conducta actual y fijar multiplicidad/instancias antes de cambiar cálculo de pasivos. |
| Azar y probabilidades | Mantener política de selección vigente salvo corrección explícita del 0% incoherente; unificar la función que calcula pesos. No adoptar 50%/75% de la demo como probabilidad remota. |
| Pools y duración | No pasar silenciosamente V2 de universo completo a pool diario ni hacer variable la duración porque exista un campo. Cambios separados y versionados si se solicitan. |
| Reinicio | Separar limpieza de demo de reinicio remoto. Un reinicio permitido crea nueva generación y no habilita nueva acreditación; revisar además la política previa sin replay. |
| Permisos y CORS | Proponer contrato invitado seguro y política de JWT inválido; aprobar explícitamente los cambios de acceso antes de ejecutarlos. No modificar configuración/permisos como efecto lateral de la auditoría. |
| Atomicidad | Verificar capacidades reales de Mongo antes de elegir almacenamiento de recibos; criterios en la fase N2. |

## 7. Contrato objetivo propuesto

### 7.1 Superficie

Recomendación: familia versionada `/api/narrative/v3`, con creación de run, lectura de snapshot, envío de comandos y consulta de recibo. La ruta concreta no es requisito del documento recibido; una fachada puede mantener funciones frontend conocidas.

- Creación: comando `INICIAR_PARTIDA` con `commandId`, fecha y selección; ámbito idempotente principal/slot porque todavía no existe run. Dos claves distintas para el mismo slot no crean dos partidas activas.
- Mutación: `runId`, `commandId`, `expectedVersion`, `type` y payload discriminado. Identidad efectiva derivada de credencial, nunca del JSON.
- Lectura: un snapshot de una versión determinada y su resultado/escena pendiente. GET no ejecuta pasivos, adquisición, azar ni avance automático.
- Recibo: consulta por run y comando, con autorización de propietario. «No encontrado» no prueba por sí solo que una solicitud todavía en vuelo no vaya a confirmar: conservar la misma clave para reintentar.

### 7.2 Snapshot y recibo

Snapshot completo para reanudar:

- `runId`, generación inmutable, `schemaVersion`, `rulesVersion`, `contentVersion`, `version`, `motor`.
- Fecha, mes, fase, status; corte separada de afinidad; inventario y tags completos.
- Política de juego/adaptación acordada e identificada por versión.
- `contenidoActual` como unión discriminada: draft, evento V1, conversación V1, nodo V2, resultado o final.
- `comandosPermitidos`, resultado pendiente y referencia de continuación cuando corresponda.
- Historial mediante proyección consistente y, si crece, lectura paginada con versión/cursor; no copiar todo el historial en cada recibo innecesariamente.

Recibo confirmado:

- Identidad del comando, hash canónico del tipo/payload/versión esperada, versión anterior y nueva.
- Snapshot resultante y consecuencias ordenadas con ID estable, origen/instancia, atributo, antes, delta solicitado, delta aplicado y después.
- Consecuencias tipadas también para tags e inventario; no forzar todo a delta numérico.
- Resultado narrativo estable, incluso con consecuencias vacías.
- Estado de liquidación económica, si aplica, separado de la victoria narrativa y de su representación.

Las proyecciones no exponen semillas, nodos futuros, destinos ponderados ni contenido secreto no permitido. El jugador no debe consultar catálogos administrativos para completar su pantalla.

### 7.3 Comandos y transiciones

| Comando | Dominio |
|---|---|
| `INICIAR_PARTIDA` | Validar selección/oferta, fijar reglas/contenido, aplicar adquisición una vez, preparar primer estado. |
| `ELEGIR_CARTA_MENSUAL` | Validar draft y cantidad, adquirir, evaluar colapso y preparar evento del motor fijado. |
| `DECIDIR_EVENTO` | Solo V1; validar toda condición aplicable, sortear y persistir resultado pendiente. |
| `RESPONDER_CONVERSACION` | Solo V1; validar opción y requisitos, persistir afinidad y resultado. |
| `AVANZAR_NODO` | Solo V2; validar grafo/nodo/opción/version, avanzar y conservar cada terminal y continuación. |
| `CONTINUAR_RESULTADO` | Reconocer ID de resultado pendiente; habilitar la siguiente escena sin reaplicar sus efectos. |
| `AVANZAR_MES` | Solo balance y sin resultado pendiente; guardar mes, aplicar política o cerrar partida. |
| Reinicio, si está permitido | Operación explícita separada, versión esperada y nueva generación; no recompensa nueva por el mismo slot. |

Arranques manuales de grafos no deben convertirse en caminos alternativos sin guardas dentro del protocolo nuevo. Mantenerlos solo si hay un caso de uso autorizado, sometidos a las mismas invariantes.

Una intención aceptada confirma una sola versión de dominio. Un rechazo no cambia estado. Una animación terminada no envía otro comando de negocio; la continuidad persistida la origina una intención explícita del jugador.

## 8. Plan completo por etapas y dependencias

Los nombres N0–N9 evitan confundir esta migración con las fases 0–5 ya realizadas. Cada etapa entrega pruebas y un criterio de salida; no se estiman fechas sin resolver decisiones de política y almacenamiento.

### N0 — Alinear bases, contrato y caracterización

Responsables: backend + frontend. Sin dependencias.

1. Publicar la matriz corregida de repositorios/SHAs y conservar el análisis original como histórico.
2. Identificar build realmente servido en cada entorno mediante artefactos/logs de despliegue; no inferirlo del nombre de repositorio.
3. Congelar fixtures V1/V2: selección, pérdidas, afinidad, tags, duplicados, probabilidades, mes 12, especiales y demo.
4. Resolver las decisiones de la sección 6 y aprobar DTOs/error codes y mapping de fases.
5. Generar OpenAPI y tipos TypeScript desde el contrato aprobado; test de deriva. No abrir Swagger productivo como requisito.
6. Asegurar el aislamiento de pruebas antes de abrir conexiones o crear índices: validar hosts y base efectivos de la URI, no solo `MONGODB_DB_NAME`. Usar Mongo efímero dedicado y un cliente ASGI sin dependencia de DB para contratos puros. La guarda actual comprueba configuración/substring del host, pero la base efectiva se comprueba después de conectar: [tests/conftest.py:24–56](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/tests/conftest.py#L24). La conexión prioriza la base de la URI y crea índices antes de esa comprobación: [app/core/database.py:25–51](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/core/database.py#L25).

**Salida:** catálogo de comandos/estados y decisiones semánticas firmado por ambos lados; pruebas aisladas que distinguen comportamiento preservado de defectos a corregir.

### N1 — Cerrar integridad en las fronteras actuales

Depende de N0 para cambios de acceso; las reproducciones aisladas pueden comenzar antes.

1. Reemplazar creación que sobrescribe por inserción exclusiva, con resolución explícita de duplicado concurrente.
2. Hacer que inicio/avance/encadenamiento de grafos calculen en memoria; quitar commits internos de helpers. El coordinador confirma todo el cambio una sola vez.
3. Proyectar estado y grafo desde la misma copia de run, evitando la segunda lectura.
4. Separar ausencia de credencial de credencial inválida. Integrar controles de servicio/cuenta que correspondan al contrato aprobado.
5. Emitir/validar identidad invitada no predecible o firmada, aislada por run. Integrar el transporte y probar proxy mismo origen y CORS si se admite origen cruzado.
6. Controlar reinicio concurrente y generación; impedir que respuestas del run anterior se apliquen al nuevo.

**Salida:** doble inicio, fallo entre preparación/commit, encadenamiento y reinicio no dejan estado parcial ni sobrescriben otra partida. Acceso cruzado e invitado compartido rechazados en el nuevo flujo.

### N2 — Persistencia de comandos, recibos y cierre económico

Depende de N0/N1.

1. Verificar en entorno aislado topología Mongo, soporte de sesiones/transacciones, write concern e índices.
2. Preferencia si existe soporte transaccional: run + recibo + resultado/consecuencias + obligación de liquidación en una transacción; índice único `(principal, runId, commandId)` y unicidad del slot de creación.
3. Si Mongo no soporta transacciones y no hay autorización para cambiar infraestructura: diseño de documento único con estado, recibo y obligación durable confirmados mediante CAS. Antes de elegirlo, medir tamaño máximo real, límite BSON de 16 MB, crecimiento de recibos y política de archivo. No podar recibos de una partida activa y luego volver a aceptar la misma clave.
4. No avanzar con «guardar run y después recibo» como aproximación temporal. La selección de almacenamiento es una puerta de salida de esta fase, no una deuda posterior.
5. Buscar recibo tras autorizar y antes de validar `expectedVersion`. Repetido idéntico devuelve el resultado original; clave reutilizada con otro hash devuelve conflicto.
6. Unificar el coordinador: cargar, validar, resolver con RNG inyectado, confirmar por CAS, responder solo el resultado ganador. Distinguir commit incierto de fallo confirmado; recuperar recibo en vez de volver a sortear.
7. Mantener RNG, reloj y catálogo como dependencias pequeñas del caso de uso. No extraer un framework genérico para todos los juegos.
8. Guardar con el cierre una obligación durable de sincronizar intento/recompensa. Consumirla idempotentemente con el ledger actual; el reconciliador debe descubrir también el cierre que aún no creó asiento.
9. Separar `rewardId`/recompensa confirmada del delta «aplicado en esta request». En invitados, el cliente acredita localmente por `rewardId` una sola vez: reenviar un recibo no vuelve a sumar puntos.

**Salida:** mismo comando en concurrencia, payload distinto, rollback, caída después del commit y cierre sin asiento no duplican efectos ni pierden la obligación de pago. Una intención nueva sobre versión vieja obtiene conflicto.

### N3 — Contenido inmutable y reglas ejecutables

Depende de N0; almacenamiento de referencias coordinado con N2. Puede trabajarse en paralelo a la extracción N1.

1. Inventariar acciones/triggers/operadores presentes en datos reales mediante diagnóstico de solo lectura autorizado. Distinguir desconocidos de enums sin handler.
2. Reutilizar el validador V2 y hacerlo obligatorio antes de que contenido sea seleccionable por runs nuevos. Validar además ECA, referencias entre colecciones/universos, recursos, límites y personajes. Validar forma/tipos antes de recorrer un payload inline, números finitos, campos requeridos por cada acción/condición, motor permitido y límites ordenados. Hoy `float` admite `NaN`/`Infinity` sin rechazo explícito y una raíz no hashable puede lanzar `TypeError`: [graph_validator.py:171–175](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/validation/graph_validator.py#L171) y [233–242](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/validation/graph_validator.py#L233). El reporte HTTP 200 del validador no es un defecto: falta exigir aprobación al publicar. La revisión de todo el catálogo debe paginar; la consulta actual limita a 500 documentos por tipo, no acredita cobertura completa.
3. Fijar una revisión inmutable del contenido completo utilizado por el run: universo/límites, desafío y pools, personajes, cartas, eventos, resultados, diálogos, grafos y finales. No fijar solo el grafo actual.
4. Cambios admin crean nueva revisión; runs activos siguen leyendo la anterior. Borrado de una edición no elimina revisiones referenciadas. Incluir todas las vías de escritura, no solo CRUD: generación mensual que reemplaza desafíos y carga manual de finales que reemplaza documentos. Revisar [challenge_service.py:126–189](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/admin/challenge_service.py#L126) y [challenge_service.py:93–110](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/admin/challenge_service.py#L93); no asumir que todo seed es no destructivo.
5. Empezar con las acciones realmente usadas y soportadas. Rechazar con diagnóstico las no ejecutables; agregar quitar tags/cartas o modificar pesos solo cuando exista contenido aprobado que lo requiera.
6. Fijar orden estable de fuentes/efectos, base porcentual y redondeo. Python `round` no equivale siempre a JavaScript `Math.round`: pruebas de empates positivas/negativas. No cambiar el resultado histórico al «unificar» implementaciones.
7. Capturar consecuencias durante la ejecución, no inferirlas luego desde un delta agregado. Adaptadores V1/V2 conservan sus disparadores pero comparten operaciones semánticas donde corresponda.
8. Mantener texto/resultado neutral; validar límites de encadenamiento y estructura de grafos. Índices/cachés incluyen revisión; ningún caché vivo cambia reglas de una partida fijada.

**Salida:** editar catálogo mientras se juega no cambia esa partida; contenido inválido no llega al runtime nuevo; todas las acciones publicables tienen implementación y pruebas.

### N4 — Primera sección vertical: avanzar mes

Depende de N2/N3 y contrato frontend de N0.

1. Implementar `AVANZAR_MES` con snapshot/recibo/consecuencias completos, reutilizando transición actual.
2. Probar con run creado mediante fixture en balance; esto es un piloto de desarrollo, no una autorización para mezclar contratos dentro de partidas productivas.
3. Construir controlador de presentación: `cargando`, `listo`, `enviando`, `resultado_incierto`, `reconciliando`, `mostrando_consecuencias`, `error_recuperable`.
4. Retirar incremento optimista del camino nuevo. Snapshot se reemplaza una vez; contador visual anima antes→después.
5. Conservar comando y payload ante timeout; reintentar misma clave. Ignorar respuesta de otra cuenta/run/generación o versión anterior.
6. Finalizar/saltar animación modifica solo cursor visual. No POST desde callbacks de animación ni desde restauración del draft.

**Salida:** arancel 60→70 una vez, clamp 95→100, condición incumplida sin efecto, mes 12 sin turno 13, recarga y conflicto sin avance local inventado.

### N5 — Inicio, adquisición y decisiones V1

Depende de N4; usa persistencia/contenido comunes.

1. Migrar inicio, corte y cartas como selección provisional hasta confirmar. La adquisición no se ejecuta en Redux remoto.
2. Migrar carta mensual y restaurar inventario/corte/tags desde snapshot completo.
3. Migrar decisión V1: validar condiciones de todas las opciones aplicables y usar una misma función de pesos para proyección/sorteo.
4. Migrar conversación: validar requisitos; respuesta autoritativa sustituye afinidad y conserva resultado textual.
5. Añadir resultado pendiente y `CONTINUAR_RESULTADO`. ID de resultado y continuación se confirman sin repetir azar ni efectos.
6. Integrar política adaptada aprobada: si se omite selección, el servidor la resuelve dentro de una transición definida, no al montar la pantalla. Preservar feedback accesible.

**Salida:** recorrido V1 completo remoto, incluyendo resultado neutral, pérdidas adaptadas aprobadas, recarga en cada fase y final sin cálculo local de derrota/victoria.

### N6 — Grafos V2, resultados y escenas encadenadas

Depende de N4 y del modelo de resultado de N5; pruebas pueden prepararse en paralelo.

1. Llevar `AVANZAR_NODO` al coordinador común; conservar opciones ocultas/deshabilitadas y destino ponderado privado.
2. Persistir terminal como resultado pendiente junto a consecuencias y referencia de continuación.
3. Si hay especial o conversación posterior, no sustituir el resultado que aún debe leerse por la raíz siguiente. Representar la secuencia pendiente.
4. Recargar cualquier nodo/terminal reproduce el mismo contenido y saldo; GET no busca nodos en la colección V1.
5. Mantener especiales de afinidad y orden de encadenamiento vigente, salvo corrección explícita. Los grafos resuelven escenas; la finalización global sigue en la lógica común de partida.
6. Verificar agotamiento/reciclaje, opciones bloqueadas, cadenas de especiales y ausencia de conversación. No convertir readiness en una prohibición de contenido válida por accidente.

**Salida:** 12 meses V2 en base aislada, sin soft-lock ni pérdida de resultado, con encadenamientos y cierre global correctos. Esto no cambia todavía el motor oficial de todos los universos.

### N7 — Cierre de frontend, demo y autoría única

Depende de N5/N6 para retirar código ya reemplazado.

1. Convertir slice remoto en estado confirmado tipado + selección/cursor visual. Retirar cálculos de adquisición, recursos, afinidad, fases optimistas e historial inventado de ese camino.
2. Mapper exhaustivo de snapshot→pantalla. Recuperar cuenta/run/versión y resultado pendiente sin consultar endpoints administrativos.
3. Comando pendiente persistido solo si es necesario para recarga, aislado por cuenta/run/generación y limpiado al cerrar sesión. Bloqueo central de acciones incompatibles.
4. Correlacionar respuestas aun después de desmontaje; abortar fetch no cancela una ejecución servidor.
5. Demo explícita y visible en todos los tamaños, espacio de almacenamiento propio y ninguna migración automática de snapshot local al servidor. Un 404/timeout no cambia autoridad.
6. Deduplicar animaciones por consecuencia y créditos locales por recompensa. Reanudar texto neutral aunque no haya deltas; soportar movimiento reducido y salto de animación.
7. Actualizar tests antiguos que validaban fallback automático, en vez de conservar esa conducta para que «sigan verdes».

**Salida:** ninguna acción de presentación cambia dominio confirmado; pruebas de StrictMode, doble clic, recarga, cambio de cuenta, respuestas tardías y falta de red pasan en navegador.

### N8 — Migración de datos, rollout y reversión

Depende de N5/N6/N7 y validación integral.

1. Inventario dry-run de runs activas/finales, contenido faltante, versión interna, resultados ambiguos y liquidaciones incompletas; usar entorno y datos autorizados.
2. Nuevos runs se crean con protocolo/reglas/contenido nuevos. Los anteriores terminan por el contrato anterior, sin alternar motor/protocolo dentro de la misma partida.
3. Si se exige convertir runs activas: solo en frontera segura y mediante migración explícita, con copia previa y validación de equivalencia. Si no existe revisión histórica, declarar que se fija el contenido disponible al migrar; no inventar versiones ni consecuencias antiguas.
4. No reconstruir resultados ambiguos ejecutando de nuevo azar/efectos. Resolverlos mediante una política de recuperación acordada.
5. Preparar índices y revisiones antes de admitir nuevas partidas; comprobar compatibilidad con clientes aún abiertos.
6. Activar por una cohorte/universo controlado cuando haya evidencia de readiness. El discriminador es persistido por run, no una colección de flags dispersos.
7. Reversión: detener nuevas altas del protocolo nuevo y conservar un servidor capaz de terminar sus runs. No devolver una run nueva a servicios viejos ni bajar versiones sobrescribiendo estado.
8. Retirar contratos viejos solo cuando no queden runs/clientes dependientes; deprecar no equivale a borrar V1 ahora.

**Salida:** despliegue y reversión ensayados con datos de prueba; no migración destructiva ni pérdida de partidas. Publicación/infraestructura requieren autorización separada.

### N9 — Observabilidad y documentación final

Se diseña desde N0; cierre después de N8.

- Logs por run/command/versión, resultado de CAS, motor, revisión de contenido y reglas; sin tokens ni payloads personales.
- Métricas de conflicto, repetición, latencia, rechazo, resultado pendiente y liquidación económica pendiente/fallida.
- Verificar que un ganador devuelve un recibo y un perdedor no publica consecuencias ni acredita puntos.
- Nueva revisión del HTML y Markdown contra ambos HEAD reales; actualizar capítulos y demos, no solo encabezado de commit.
- Guía del frontend con problema→solución→acción y contraste V1/V2; distinguir propuesta, contrato soportado y comportamiento desplegado.
- Conservar pruebas del panel y su página de diagnóstico al compilar admin si hubo cambios de validación. No rediseñar el visor como parte de esta etapa.

**Salida:** un desarrollador puede identificar backend/protocolo/motor, reproducir aceptación y diagnosticar un comando incierto sin apoyarse en capturas o documentación histórica.

## 9. Pruebas de aceptación obligatorias

| Nivel | Casos |
|---|---|
| Dominio puro | Fijo/porcentual, redondeo, límites del universo, recursos/personajes ausentes, orden, tags, copias según política, condiciones secretas y no secretas, conversación neutral, adaptación. |
| FSM dominio | Todas las transiciones permitidas/rechazadas por motor; resultado pendiente impide avanzar; terminales y especiales; ninguna mutación después de final. |
| HTTP + Mongo aislado | Doble inicio; mismo comando simultáneo; clave reutilizada; dos claves con misma versión; fallo antes del commit; respuesta perdida después; commit incierto; reinicio concurrente; contenido editado/borrado. |
| Proyecciones | Snapshot de una sola versión; corte/inventario/tags completos; terminal V2 y conversación V1 reanudables; ausencia de semillas/destinos/secretos futuros. |
| Economía | Cierre sin asiento reparable; intento/ledger coherentes; usuario y guest; recompensa repetida no acreditada otra vez; reinicio sin nueva recompensa de slot. |
| Frontend | Doble clic, StrictMode, timeout, respuesta vieja/otra cuenta/otro run, desmontaje, recarga en cada fase, neutral sin deltas, movimiento reducido y salto visual. |
| E2E | Corte→cartas→evento→resultado→conversación opcional→balance→12 meses/final para V1 y V2, con cuenta e invitado y política adaptada aprobada. |
| Regresión | Clásicos/scoring, economía, SSO, permisos admin, editor de grafos y hosting `/admin` conservan contrato. |

Las pruebas en memoria caracterizan lógica y contratos, pero no certifican atomicidad Mongo, índices reales ni comportamiento multi-proceso. La aceptación de N2 requiere base aislada real y pruebas de fallo, no solo mocks que implementen un `$inc`.

El readiness existente tampoco sustituye el E2E de doce meses: utiliza estado sintético con personajes/cartas y su propia aplicación de impactos con límites 0–100, sin recorrer por HTTP el ciclo mensual, las pasivas, la economía y todas las transiciones especiales. Ver [scripts/v2_readiness.py:135–156](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/scripts/v2_readiness.py#L135) y [250–334](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/scripts/v2_readiness.py#L250). Antes de tomar la suite histórica como aceptación, actualizar expectativas antiguas de admin sin autenticación y raíz terminal en [tests/test_narrative_v2_admin.py:12–18](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/tests/test_narrative_v2_admin.py#L12) y [88–113](file:///C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/tests/test_narrative_v2_admin.py#L88), sin relajar controles actuales para hacerlas pasar.

## 10. Verificación realizada y próximos pasos

- Git/SHAs y diferencia de bases comprobados sin sincronizar ni modificar ramas.
- OpenAPI local consultado; rutas presentes. No se ejecutaron comandos de juego sobre la base local ni productiva desde esta auditoría.
- Laboratorio documental: diez pruebas aprobadas con `node --test docs/componentes/patron-narrativo.test.mjs`; alcance limitado al modelo en memoria.
- Backend: 34 pruebas seguras aprobadas —17 del validador, 5 de identidad, 10 de readiness, 1 de discriminador/deprecación y 1 de snapshot OpenAPI— sin conexión Mongo, con destino de seguridad loopback puerto 1 y caché/bytecode desactivados. Solo se observaron advertencias de configuración Pydantic antigua en progreso.
- No se ejecutaron los 30 contratos narrativos dependientes de DB ni la integración histórica. No se afirma que la suite completa pase. Las sondas puras del validador confirmaron aceptación de pesos no finitos y condición inline desconocida, error ante raíz lista y ausencia de restricciones semánticas de algunos esquemas; se incorporaron como trabajo de N3.
- La auditoría estática respalda los defectos descritos; su frecuencia en producción no fue medida.
- No se modificó implementación, configuración, permisos, pipeline ni memorias persistentes. Este documento es el entregable del plan; no se hicieron commits ni pushes.

**Siguiente paso recomendado:** ejecutar N0 y la caracterización de N1; acordar identidad, contrato y almacenamiento antes de convertir el piloto `AVANZAR_MES` en funcionalidad productiva. La primera entrega no debe ser otro motor: debe ser una transición real, confirmada una sola vez y recuperable de extremo a extremo.
