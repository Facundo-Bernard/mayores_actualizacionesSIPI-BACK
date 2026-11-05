# Meta Prompting — Alineamientos Backend

## Uso de esta carpeta

Estos documentos son instrucciones para agentes que ejecutarán etapas de la evolución narrativa. **Redactar estos prompts no autoriza a ejecutarlos.** Cuando el usuario solicite una etapa, leer esta guía y su prompt, verificar las dependencias y trabajar únicamente en ese alcance. No ejecutar automáticamente la etapa siguiente.

La [auditoría y plan integral](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md) fundamenta el trabajo. Sus recomendaciones son propuestas, no decisiones aprobadas. La aprobación del usuario para esta carpeta exige **consultar y detener el trabajo afectado antes de resolver decisiones pendientes**.

Los prompts se complementan con el código actual: si una ruta, símbolo o contrato cambió, localizar su equivalente y explicar la diferencia. No recrear archivos eliminados para obedecer una referencia histórica. Los archivos citados son puntos de entrada, no una lista que autorice modificar cualquier dependencia. Leer también las instrucciones vigentes de cada repositorio antes de editarlo.

Para invocar una etapa, el usuario puede indicar: «Ejecutá N0 de esta carpeta; respetá la guía común y detenete en las decisiones pendientes». Para revisar sin implementar: «Revisá las dependencias y preguntas de N2, sin modificar código». En ambos casos el agente debe mantener la frontera solicitada; leer un prompt no inicia los demás.

## Base y procedencia

Comprobación del 5 de noviembre de 2026:

- El usuario identifica como backend de producción `https://github.com/JNicolasFernandezG/juegos-mayores-actualizaciones-back.git`, rama `main`.
- `git ls-remote prod-games refs/heads/main` devolvió `9cb670ca4fdc16b9940fa84d8204eb66bdd94b46`.
- El checkout backend estaba en `feature/refactor-backend@7b865637756cbf28add5899c2fd053c927254bb4`. Su diferencia con esa referencia era únicamente el build del panel admin; no la lógica de aplicación.
- Esto identifica el repositorio de referencia y su rama remota, **no certifica el SHA realmente desplegado ni ausencia de regresiones productivas**.
- El documento de arquitectura recibido analizó `Facundo-Bernard/main@33cdf8f`. No utilizarlo como inventario actual de funcionalidades: nuestro backend ya contiene motores V1/V2, OCC, ledger, economía, admin y SSO.

Ruta de trabajo al redactar:

- **B**: `C:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK`.
- El worktree hermano `sipi-estable` no pertenece automáticamente al alcance.
- El frontend es responsabilidad de otro desarrollador. N0–N10 no autorizan editar ese repositorio, instalar dependencias, generar TypeScript, compilar clientes ni ejecutar sus pruebas UI. La integración se coordina mediante OpenAPI, contratos y evidencia externa.

Al ejecutar, comprobar `git status`, rama, remotos y SHA del backend. Comparar `main` del repositorio productivo, no asumir que `origin/main` representa producción. Una consulta remota de solo lectura no autoriza merge, checkout, pull ni push. Si la referencia local quedó atrás, comunicarlo y acordar cualquier sincronización necesaria; no comparar silenciosamente con datos obsoletos.

## Secuencia de prompts

| Prompt | Dependencia y entrega |
|---|---|
| [N0 — Bases, contrato y caracterización](N0-bases-contrato-y-caracterizacion.md) | Sin dependencia; establece evidencia, decisiones, pruebas aisladas y OpenAPI objetivo backend. |
| [N1 — Integridad e identidad](N1-integridad-e-identidad.md) | N0 para cambios de acceso; creación exclusiva, confirmación única y lectura coherente. |
| [N2 — Comandos, recibos y economía](N2-comandos-recibos-y-economia.md) | N0/N1; persistencia atómica e idempotencia del protocolo nuevo. |
| [N3 — Contenido y reglas](N3-contenido-versionado-y-reglas.md) | N0; coordina almacenamiento con N2 y puede avanzar en paralelo con N1. |
| [N4 — Piloto de avance mensual](N4-piloto-avance-mensual.md) | N2/N3 y contrato N0; primera sección vertical backend aislada. |
| [N5 — Inicio y conversión a V2](N5-inicio-y-flujo-v1.md) | N4; inicio/adquisición común, resultado persistido y conversión condicional de contenido V1 a grafos. |
| [N6 — Grafos y continuaciones](N6-grafos-v2-y-continuaciones.md) | N4 y modelo de resultado N5; recorrido V2 backend. |
| [N7 — Entrega de integración](N7-frontend-autoritativo-y-demo.md) | N5/N6; paquete OpenAPI y compatibilidad backend para el consumidor externo. |
| [N8 — Migración y reversión](N8-migracion-y-reversion.md) | N5/N6/N7 y evidencia externa de integración; ensayo antes de publicación autorizada. |
| [N9 — Observabilidad y documentación](N9-observabilidad-y-documentacion.md) | Diseñar desde N0; instrumentar progresivamente y cerrar tras N8 con documentación backend. |
| [N10 — HTML integral del backend](N10-documentacion-html-backend.md) | Cierre documental después de N0–N9; HTML exclusivo del backend, con evidencia y correspondencias al documento original. |

N9 alinea documentación existente y observabilidad; N10 produce una nueva referencia HTML integral del backend tomando el HTML recibido como modelo editorial, sin reemplazarlo. N10 consume las decisiones D01–D11 aprobadas, no las resuelve ni autoriza implementación o publicación adicional.

Una dependencia se satisface con código, contrato aprobado y evidencia de pruebas, no porque exista su Markdown o un agente haya dicho «terminado». Se pueden preparar pruebas o contratos independientes en paralelo; no editar simultáneamente los mismos módulos sin coordinación.

## Registro de decisiones y paradas obligatorias

**Estado vigente en el [registro de decisiones](01-registro-de-decisiones.md):** D01–D05 y D07–D09 fueron aprobadas el 5 de noviembre de 2026; D06 quedó diferida y D10/D11 se deciden en N8/N9. El usuario también aprobó el **retiro del motor V1 y sus rutas**: el protocolo `/v3` es solo V2 y el contenido V1 de eventos/conversaciones se convierte a grafos solo si falta. La tabla siguiente describe qué decide cada ID; para su estado, mirar el registro.

Antes de este registro, toda recomendación de la auditoría era solo propuesta. Si una respuesta explícita posterior cambia una decisión, actualizar el registro citando la evidencia; no reabrir decisiones aprobadas por cuenta propia.

| ID | Decisión que requiere acuerdo | Etapas afectadas |
|---|---|---|
| D01 | Superficie/versionado del protocolo, DTOs, errores y coexistencia con clientes anteriores. `/api/narrative/v3` es una propuesta, no una ruta aprobada. | N0/N2/N4–N8 |
| D02 | Fases, resultado pendiente, reconocimiento explícito y continuación; mapping de `completed/game_over`. | N0/N4–N7 |
| D03 | Identidad invitada verificable, JWT inválido, cuenta/servicio, transporte, permisos y CORS. | N0/N1/N7/N8 |
| D04 | Duplicados/copias, recursos/personajes ausentes, orden de efectos y redondeo; separar defectos de cambios de reglas. | N0/N3/N5 |
| D05 | Corrección de pesos 0%, probabilidades de conversación, pools y duración. Preservar políticas vigentes salvo cambio expresamente aprobado. | N0/N3/N5/N6 |
| D06 | Adaptación de dominio por edad, atenuación, selección automática y preferencias de conversación. No convertir el 50% local en regla remota sin aprobación. | N0/N4/N5/N7 |
| D07 | Reinicio remoto, no replay, generación de run y recuperación de runs anteriores. | N0/N1/N5/N8 |
| D08 | Transacciones o documento único, retención de recibos, política de RNG y recuperación, recibo económico y `rewardId`. | N0/N2/N3/N7/N8 |
| D09 | Publicación/revisiones de contenido, tratamiento de contenido inválido existente y revisiones referenciadas. | N0/N3/N6/N8 |
| D10 | Cohorte, migración de runs activos, datos ambiguos, índices, activación y reversión. | N8 |
| D11 | Señales observables, acceso, retención, umbrales y cualquier servicio externo. | N9 |

### Cómo actuar ante una parada

1. Verificar si la decisión tiene aprobación explícita y aplicable; no inferirla del silencio, de defaults o de otro agente.
2. Exponer el hallazgo, la pregunta concreta, alternativas y recomendación con impacto en compatibilidad, datos y pruebas.
3. Detener **solo el tramo dependiente** antes de escribir su implementación. Se permite inspección y caracterización local independiente, no una solución provisional que cambie producto.
4. Informar qué sigue bloqueado y qué trabajo seguro queda. Si no queda trabajo independiente, esperar respuesta del usuario.
5. Registrar la decisión y su evidencia en el traspaso de la etapa. No modificar el estado de esta tabla como si el agente fuera quien aprueba.

## Invariantes y exclusiones comunes

- Reutilizar Python/FastAPI/MongoDB, motores existentes, repositorios y ledger. No introducir microservicios, event sourcing completo ni otro motor TypeScript por defecto.
- Distinguir versión de API, motor V1/V2, schema, reglas y contenido. Una URL `/v2` no convierte una partida en motor V2.
- Preservar tres personajes y tres cartas iniciales, una elección mensual y doce meses; cambios de balance requieren decisión explícita.
- Mantener recompensas narrativas y economía local del invitado. Proteger identidad de run no autoriza crear saldo invitado server-side. Reintentar HTTP no equivale a rejugar para cobrar de nuevo.
- No rediseñar grafos, clásicos, scoring, vidas ni imágenes. No cambiar pipelines, configuración sensible, permisos ni infraestructura sin autorización específica.
- No commit, push, publicación, migración o escritura en DB compartida/productiva por ejecutar un prompt. Esas acciones requieren autorización separada.
- Preservar modificaciones ajenas y archivos no rastreados. No reset, clean, borrado de ramas ni stash global como atajo; detenerse ante conflicto de trabajo.
- Nuevos contratos no deben romper clientes vigentes ni dejar que endpoints antiguos muten runs del protocolo nuevo.

## Reglas de verificación

Antes de cualquier prueba Mongo, comprobar URI, hosts y base efectivos **antes de conectar o crear índices**. La guarda histórica comprueba parte de esto demasiado tarde; fijar solo `MONGODB_DB_NAME` no garantiza aislamiento. Usar base efímera dedicada con fixtures propios y limpieza acotada, no IDs del catálogo real.

Las pruebas puras y los laboratorios no demuestran atomicidad multi-proceso ni E2E. El readiness sintético V2 no sustituye doce meses por HTTP con pasivas, economía y encadenamientos. No relajar autenticación o validadores para mantener expectativas históricas incorrectas.

Para cambios UI, iniciar servidor de desarrollo en un puerto libre acordado, probar el flujo real en navegador, recarga, errores y regresiones, y revisar consola/red. Si no es posible, declarar la validación pendiente. Si se compila admin, preservar `B/app/static/admin/test-narrativo.html`: el build puede vaciar el directorio de salida. No modificar `.env` ni sobrescribir procesos ajenos silenciosamente.

## Entrega estándar de cada etapa

Entregar: objetivo logrado; archivos y símbolos modificados; contratos antes/después; decisiones aplicadas con evidencia; comandos de prueba y resultados reales; pruebas no ejecutadas y motivo; riesgos pendientes; dependencias que quedan habilitadas. No declarar «listo para producción» por tests unitarios ni marcar completa una etapa bloqueada o con aceptación parcial.

Mantener una diferencia pequeña y revisable. Las decisiones documentales y los resultados de pruebas se comunican sin secretos ni datos personales. Cualquier subagente recibe esta misma frontera de autorización; delegar no amplía permisos.
