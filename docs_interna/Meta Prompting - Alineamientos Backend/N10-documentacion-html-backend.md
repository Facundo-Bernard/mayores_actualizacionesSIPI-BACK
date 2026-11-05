# N10 — Documentación HTML integral y exclusiva del backend

## Rol y misión

Cuando el usuario invoque esta etapa final, actuá como responsable de documentación técnica y verificación del backend. Generá un HTML navegable, completo y pedagógico que demuestre la arquitectura, contratos, comportamiento y límites del backend realmente resultante de N0–N9. **Ahora este archivo es únicamente un prompt: su creación no ejecuta N10 ni genera el HTML.**

Tomá como modelo de profundidad y presentación el HTML de arquitectura recibido desde el frontend. No hagas una landing page, un resumen ejecutivo aislado ni una transcripción del plan como si ya estuviera implementado. El entregable debe permitir incorporarse al proyecto, seguir un request hasta sus efectos, reproducir verificaciones y diagnosticar fallos sin depender de esta conversación.

El alcance es **todo el backend de juegos verificado**, no solo el motor narrativo ni los cambios recientes. «Demostrar todo» significa cobertura trazable del alcance inventariado, con ejemplos, evidencia y límites explícitos; nunca publicar secretos ni presentar hechos no comprobados como garantías.

## Lectura obligatoria y modelo editorial

Leé la [guía común](00-guia-de-ejecucion.md), la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md), las entregas efectivas N0–N9 y el traspaso de [N9](N9-observabilidad-y-documentacion.md). La existencia de sus Markdown no prueba que se ejecutaron.

B y F son los repositorios definidos en la guía. Revisá completos:

- F: `arquitectura-cognijuegos.html`, incluidos estilos, JavaScript, capítulos, fuentes, navegación y modo impresión.
- F: `docs/arquitectura/motor-acciones-y-maquina-de-estados.md` y los módulos locales que el HTML utiliza, para entender sus propuestas y el alcance de sus demostraciones. No copiarlos ciegamente.
- B: `docs_interna/refactor/06-auditoria-arquitectura-y-plan-narrativo.md`, las decisiones aprobadas durante la ejecución y documentación vigente de contratos/operación.
- B: instrucciones del repositorio, entrada de aplicación, routers realmente incluidos, esquemas, servicios, repositorios, índices, tareas programadas, configuración, pruebas y artefactos de despliegue autorizados. Localizar estos elementos en el checkout vigente.

El modelo recibido tiene 18 capítulos, índice lateral agrupado, navegación anterior/siguiente, búsqueda, tema claro/oscuro, avance de lectura local, fichas/tablas, mapas y recorridos interactivos, ejemplos copiables, referencias y salida de impresión. Conservar ese nivel de utilidad, no su inventario desactualizado ni su arquitectura frontend. Sus capturas ilustran UI, no prueban estado del backend.

## Dependencias y evidencia requerida

La edición final depende de N0–N9 completadas dentro de su alcance aprobado: contratos, pruebas, decisiones, límites de migración y observabilidad. Se puede preparar inventario/estructura antes, pero no declarar un cierre final mientras haya entregas requeridas sin verificar. Si el usuario pide una edición intermedia, identificarla como borrador de alcance parcial y enumerar qué falta.

Revalidar en cada ejecución:

1. Repositorio backend de referencia indicado por el usuario: `https://github.com/JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, rama `main`.
2. SHA remoto, checkout analizado, cambios locales y fecha del análisis. Los valores `9cb670c` y `7b86563` de la guía son históricos, no la base perpetua.
3. SHA o artefacto desplegado solo si hay evidencia autorizada. Merge, push, respuesta OpenAPI y pruebas locales no certifican por sí solos producción.
4. Base del HTML original: verificar sus fuentes. En la revisión recibida analizaba el backend educativo `Facundo-Bernard/main@33cdf8f`; no confundir diferencia de repositorio con una funcionalidad agregada por esta migración.

## Entregable y frontera de autorización

Crear por defecto **B:`docs_interna/arquitectura-backend.html`**, en español, con título inequívoco «CogniJuegos — Arquitectura del backend». Si ya existe, leerlo, verificar autoría/cambios pendientes y actualizarlo de forma acotada; no sobrescribir trabajo ajeno. El archivo debe ser portable y poder consultarse sin montar el panel admin.

Preferir HTML semántico con CSS, SVG y JavaScript locales/autocontenidos, sin CDN, fuentes remotas, analítica ni dependencias nuevas. Si un anexo técnico real requiere assets, mantenerlos junto a la documentación y entregar su inventario; no usar imágenes de UI como sustituto de evidencia backend.

No modificar aplicación, DB, permisos, CI/CD, infraestructura ni contrato para que coincidan con lo documentado. No montar otra ruta pública para servir el HTML. No publicar, commitear ni pushear. N9 conserva su tarea de alinear documentación existente; N10 crea esta obra backend nueva, sin sobrescribir el HTML original del frontend.

Mencionar clientes únicamente como actores externos de un contrato backend. Excluir capítulos sobre componentes React, Redux, estilos de pantallas, Capacitor o diseño de juegos del cliente. Sí documentar el contrato HTTP, identidad, requisitos de consumo y cómo el backend sirve `/admin` y otros estáticos: no explicar por eso la arquitectura visual del panel.

## Paradas obligatorias

- **Decisiones D01–D11:** comprobar aprobación y estado implementado antes de presentar cualquier recomendación como contrato vigente. Si hay discrepancia, marcarla y consultar antes de cambiar significado; no resolverla editando código.
- **Dependencias de cierre:** si una entrega necesaria sigue bloqueada, detener la afirmación de completitud. Presentar faltantes y preguntar si se espera el cierre o se solicita expresamente un borrador parcial.
- **D03/D11 — información sensible:** antes de incorporar trazas, identificadores, configuración, datos de usuarios o exportaciones reales, confirmar que el material está autorizado y sanitizado. Usar fixtures sintéticas por defecto. Nunca incrustar tokens, PIN, cookies, secretos, URIs con credenciales o contenido personal.
- **D10 — producción:** antes de consultas operativas o pruebas sobre servicios compartidos, pedir autorización específica. La documentación puede declarar despliegue no verificado sin inventar pruebas ni requerir acceso productivo para avanzar con evidencia local.
- Si una prueba revela un defecto nuevo, registrarlo con alcance y reproducción segura; detener cualquier afirmación contradicha. Corregir la aplicación requiere una tarea autorizada aparte, no es un efecto lateral de N10.

## Método de evidencia y correspondencia con el original

Para cada afirmación significativa, registrar: ID estable, afirmación concreta, tipo de evidencia, ubicación/símbolo, revisión, prueba/observación relacionada y límite. Distinguir **observado en código**, **verificado por prueba**, **observado en entorno**, **propuesto/pendiente**, **no verificado** y **no aplicable al backend**. Un badge no reemplaza el detalle.

Usar enlaces de código fijados a commits verificados cuando el código exista en ese commit. Si solo existe en cambios locales, declararlo como tal: no inventar un enlace remoto al HEAD anterior. En la edición portable preferir referencias relativas verificadas o enlaces de repositorio estables; no depender de rutas personales `C:/Users/...`. Los enlaces externos a fuentes pueden necesitar red, pero el texto, diagramas y demostraciones deben funcionar sin ella.

Crear una matriz central y referencias junto a cada apartado que responda al original. Cada fila debe incluir:

- Capítulo, ancla y revisión del HTML original; afirmación citada brevemente o paráfrasis identificada como tal.
- Relación: **confirma**, **completa**, **corrige para esta base**, **implementa una propuesta**, **sigue pendiente** o **no aplica al alcance backend**.
- Qué existía antes del alineamiento, qué cambió durante N0–N9 y cuál es el estado actual.
- Fuente actual, prueba disponible, limitaciones y enlace al desarrollo en este HTML.

No atribuir a esta migración capacidades que ya existían. Revisar especialmente routers narrativos/grafos, economía, ledger, SSO, expiración JWT, campos de intentos, admin servido por backend y diferencias de puertos/despliegue. No copiar las correcciones históricas sin contrastarlas al momento de ejecución. Tratar el documento original con precisión: una conclusión sobre otro corte no es automáticamente falsa en su contexto.

## Cobertura mínima de capítulos

Organizar los capítulos en grupos navegables. Se pueden ajustar títulos/agrupaciones, pero no omitir silenciosamente áreas activas ni limitar todo a narrativa. Para cada módulo inventariado incluir responsabilidad, entradas, salidas, dependencias, persistencia, validaciones, fallos y pruebas; si no tiene alguno, explicarlo.

| Capítulo | Contenido demostrable requerido |
|---|---|
| 1. Alcance y lectura | Público técnico, fecha, revisión, repositorio/SHAs, leyenda de evidencias, qué se verificó y qué no. Diferenciar código local de despliegue. |
| 2. Mapa de arquitectura | Límites del backend, autenticador y Mongo como sistemas externos cuando corresponda; capas y dirección real de dependencias. Mapa interactivo con responsabilidades y fuentes. |
| 3. Arranque y ejecución | Entrada FastAPI, routers/mounts, lifespan, middlewares, dependencias, recursos y tareas de fondo; dónde se ejecuta I/O y trabajo pesado. |
| 4. Inventario de módulos | Todas las features/capacidades del checkout, activas, administrativas, legacy, auxiliares o no expuestas. Incluir módulos ajenos a narrativa que sigan presentes, sin inferir que una carpeta implica ruta registrada. |
| 5. Identidad y autorización | Login, JWT, servicio/cuenta, SSO, invitados, propiedad de runs, roles y credenciales inválidas. Fronteras de confianza y dependencia externa, no manual del autenticador ajeno. |
| 6. Catálogo de contratos | Todos los métodos/rutas backend soportados, incluidos admin/legacy y mounts pertinentes. DTOs, campos, validaciones, autorización, errores y efectos; separar API, motor, schema, reglas y contenido. |
| 7. Datos y persistencia | Colecciones, documentos/relaciones, claves e índices únicos, versiones, lifecycle, retención y migraciones. Distinguir configuración de índices de índices comprobados en una base real. |
| 8. Desafíos y juegos clásicos | Generación por juego realmente presente, validación/solución/calificación que hace o no hace el servidor, dificultad, fechas, intentos y guardado. No atribuir scoring frontend al backend por similitud. |
| 9. Economía e intentos | Ledger, idempotencia, saldo, pistas/vidas si corresponde, racha, dificultad, recompensas y reconciliación; cuenta versus invitado y prohibición de nueva acreditación del mismo slot. |
| 10. Ciclo narrativo | Setup, corte, inventario, draft, evento/conversación, balance, cierre; motor V1 frente a V2; guardas, estados y doce meses conforme política final aprobada. |
| 11. Comandos y atomicidad | Versión esperada, propietario, hash, recibos, resultado incierto, RNG, CAS, unidad de commit y obligaciones económicas realmente implementados. Señalar ausencias si quedó alcance pendiente. |
| 12. Reglas y consecuencias | ECA/condiciones/acciones soportadas, orden, pesos, redondeo, clamps, tags, afinidad, copias y adaptación aprobada; ejemplos antes/delta solicitado/delta aplicado/después. |
| 13. Contenido y administración | Catálogos, revisiones, validación, generación y seeds, publicación y borrado seguro. Rutas admin y hosting estático como responsabilidad backend, sin rediseño ni internals de UI. |
| 14. Seguridad y límites | Autorización, CORS, rate limits, validación, tamaños, secretos y límites de exposición; lo que los controles cubren y lo que no. No denominar esto auditoría de seguridad integral. |
| 15. Entorno y operación | Dependencias/versiones comprobadas, instalación, variables por nombre/propósito sin secretos, arranque local seguro, jobs y topología declarada/observada. Puertos por entorno, no defaults universales. |
| 16. Pruebas y demostraciones | Matriz de pruebas puras, contrato, Mongo, E2E y operación; comandos reproducibles, fixtures y evidencia de éxito/fallo/limitaciones. Laboratorios etiquetados como didácticos. |
| 17. Migración y reversión | Coexistencia de protocolos, runs antiguos/nuevos, contenido fijado, compatibilidad y cierre de deuda; ensayo versus rollout observado. No presentar una reversión destructiva como procedimiento seguro. |
| 18. Diagnóstico y mantenimiento | Casos síntoma→causa posible→verificación→acción, observabilidad y recuperación; puntos de extensión por feature y riesgo conocido, sin ejecutar negocio al diagnosticar. |
| 19. Respuesta al documento recibido | Matriz completa de correspondencias por capítulos/afirmaciones backend; clasificar apartados exclusivamente frontend como fuera de alcance sin reescribirlos. |
| 20. Glosario, fuentes y límites | Definiciones, registro de evidencias, comandos utilizados, decisiones, pendientes, resultados no verificados y método de actualización futura. |

La cobertura de contratos debe reconciliarse con routers/OpenAPI del mismo corte: mostrar conteos y explicar exclusiones, rutas ocultas del esquema y mounts estáticos. No copiar el número histórico de rutas como aceptación. No enviar al lector a OpenAPI para evitar documentar los campos, respuestas y errores relevantes.

## Demostraciones obligatorias

Construir diagramas/recorridos de secuencia y ejemplos concretos con fixtures sintéticas. Cada ejemplo indica entrada, guardas, funciones/capas atravesadas, lectura/escritura, salida esperada y evidencia real o carácter ilustrativo.

1. Request autenticado y request invitado: identidad efectiva y rechazo de acceso a otra run según contrato aprobado.
2. Desafío clásico→intento→validación/calificación aplicable→obligación/crédito; reintento sin duplicación. Explicar lo que el backend no verifica.
3. Mes narrativo V1 y recorrido V2 con terminal/continuación; reanudación de resultado neutral y cierre de mes doce.
4. Efecto +10 sobre 60 y clamp sobre 95 con máximo 100, usando un recurso definido en la fixture; afinidad cero y consecuencia no numérica. No generalizar ese máximo a todos los universos.
5. Mismo comando repetido, misma clave con payload distinto, dos comandos con versión común y dos inicios del mismo slot. Mostrar ganador, rechazo y estado final.
6. Respuesta perdida después del commit y cierre previo a entrega económica: recuperación por recibo/obligación, sin resorteo ni doble premio.
7. Edición/publicación de contenido durante una run fijada y convivencia legacy/nuevo durante reversión ensayada.

Solo demostrar como implementados los mecanismos verificados. Si un caso no existe o falla, presentarlo como límite o pendiente, no falsear un resultado verde. Las animaciones didácticas deben mostrar estados/paquetes trazados, no crear un segundo motor de reglas en JavaScript. No llamar a APIs reales, usar cuentas ni escribir en DB desde el HTML; las pruebas reales se ejecutan aparte, autorizadas y aisladas.

## Diseño e interacción exigidos

- Índice lateral por grupos, capítulo activo, enlaces profundos, anterior/siguiente y búsqueda por concepto, endpoint, archivo y evidencia; contemplar resultado vacío y navegación atrás/adelante.
- Jerarquía editorial equivalente al modelo, tablas legibles, notas de advertencia y filtros de contratos/estado. Usar iconos SVG sobrios, no emojis.
- Tema claro/oscuro, progreso de lectura opcional local con namespace propio, copiar ejemplos y reiniciar únicamente preferencias del documento. Si storage o clipboard no están disponibles, mantener texto y navegación utilizables.
- Diagramas locales con alternativa textual, controles por teclado, foco visible, labels, contraste, tamaños adaptables y movimiento reducido. Lo esencial debe leerse sin JavaScript.
- Impresión/PDF de **todo** el contenido, aunque haya capítulos, filtros o detalles colapsados en pantalla. No omitir filas por el estado del buscador.
- Escapar ejemplos, cadenas del buscador y datos insertados; preferir `textContent`/DOM seguro a HTML dinámico no confiable. Ningún bloque copiable contiene credenciales ni comandos destructivos listos para ejecutar accidentalmente.
- Portabilidad sin depender del checkout frontend ni de servicios web para renderizar. Los enlaces al modelo original identifican su revisión, aunque ese archivo no se distribuya junto al entregable.

## Secuencia de ejecución

1. Verificar working tree, bases y entregas. Leer el HTML modelo y extraer su estructura editorial sin adoptar sus afirmaciones como actuales.
2. Inventariar backend completo y construir matriz módulo/ruta/contrato/dato/prueba y registro de evidencias. Revisar módulos de bajo nivel y transversales, no solo endpoints felices.
3. Construir matriz de correspondencias con el original y separar capacidades preexistentes, cambios ejecutados y pendientes. Resolver paradas aplicables.
4. Redactar capítulos y ejemplos desde evidencia. Revisar técnicamente las afirmaciones antes de diseñar interacciones; enlazar las fuentes junto al punto explicado.
5. Implementar HTML y laboratorios locales con estructura accesible y contenido estático suficiente. No agregar herramientas ni infraestructura ajenas a la documentación.
6. Ejecutar pruebas autorizadas necesarias para sostener afirmaciones y registrar resultado/entorno. Antes de Mongo, validar host/base efectiva de URI antes de conexión/índices; nunca tomar el `.env` local como autorización para escribir datos.
7. Servir el documento con un servidor local de vista previa en puerto libre y probarlo en navegador, además de apertura directa/offline cuando el entorno lo permita. No iniciar procesos productivos para revisar una página documental.
8. Revisar cobertura, exactitud, enlaces, búsqueda, navegación, dispositivos estrechos, teclado, temas, impresión, ausencia de red inesperada y consola. Separar tests del documento de tests del backend que sustentan su contenido.
9. Entregar HTML/asset inventory, instrucciones de apertura, evidencia de revisión y límites pendientes. No publicar ni modificar la implementación al cerrar.

## Pruebas y criterios de aceptación

- [ ] Existe HTML exclusivo del backend, no una reescritura del frontend ni un resumen de narrativa.
- [ ] Todas las áreas activas del inventario y todos los contratos soportados tienen cobertura; las exclusiones son explícitas y justificadas.
- [ ] Afirmaciones, diagramas y ejemplos tienen fuente/estado verificable; se distingue evidencia estática, pruebas, entorno y propuesta.
- [ ] Cada respuesta al original identifica capítulo/afirmación y tipo de relación; no atribuye capacidades preexistentes a trabajo nuevo.
- [ ] Los recorridos cubren éxito, rechazo, concurrencia, recuperación, finalización y límites con fixtures sanitizadas; simulación no se presenta como integración.
- [ ] Links, anclas, conteos, filtros y referencias corresponden al mismo corte; no hay hashes inventados ni código local enlazado a un commit que no lo contiene.
- [ ] Navegación, buscador, temas, copiar, teclado, móvil y reduced-motion se probaron en navegador; impresión incluye todo, incluso contenido filtrado/colapsado.
- [ ] No hay tokens/datos personales, ejecución real desde demos, dependencias remotas de renderizado, errores de consola ni interpolación insegura.
- [ ] No se certifica producción sin evidencia; no se declaran pruebas no ejecutadas ni alcance inconcluso como completado.

## Entrega y cierre

Informar ruta del HTML y assets si existen, revisión de código, capítulos y cobertura, evidencia de correspondencias, verificaciones realizadas y limitaciones. Explicar cómo abrirlo y mantenerlo. Si no pudo probarse navegador, alguna dependencia o una afirmación necesaria, declarar esa aceptación pendiente y no presentar el documento como cierre definitivo.

El usuario recibe una referencia backend comprobable y una respuesta técnica trazable al primer HTML, no una promesa de capacidades ni una publicación automática.
