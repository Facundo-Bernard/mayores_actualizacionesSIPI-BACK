# N4 — Piloto vertical de avance mensual

## Rol y misión

Actuá como responsable de una entrega vertical backend. Al ejecutar N4, hacé que una intención explícita de avanzar mes produzca una única transición confirmada, recuperable tras timeout y proyectada en snapshot/recibo sin delegar dominio al consumidor. Este piloto de desarrollo no habilita partidas productivas que alternen protocolos.

Leé la [guía común](00-guia-de-ejecucion.md), contratos/entregas [N0](N0-bases-contrato-y-caracterizacion.md), [N2](N2-comandos-recibos-y-economia.md), [N3](N3-contenido-versionado-y-reglas.md) y N4 de la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md).

## Contexto y fuentes

El servicio vigente guarda el balance del mes; si llegó a doce, finaliza. En meses anteriores incrementa mes, aplica pasivos, evalúa colapso y prepara draft. Preservar ese orden salvo decisión expresa. La auditoría frontend es contexto histórico para evitar autoridad duplicada, no una asignación de trabajo sobre ese repositorio.

Entradas B: `app/features/narrative/game/transition_service.py` (`avanzar_mes`), `game/endings_service.py`, `engine/rule_engine.py`, `schemas/game_schemas.py`, `schemas/v3_contract_schemas.py`, `v3_openapi.py`, más el coordinador y las proyecciones realmente entregados por N2/N3.

## Dependencias y límites

N2 debe demostrar recibos atómicos, reintentos y autorización; N3 debe aportar contenido/reglas fijados y consecuencias reales. D01/D02 de N0 deben definir contrato y representación de resultado. Si falta alguna garantía, prepará fixtures y tests, no la simules con respuestas fabricadas ni persistencia doble.

Usá una run en balance creada por fixture propia en DB aislada. No conviertas una run real legacy al protocolo nuevo para demostrar el piloto. No implementes todavía todo inicio, grafos V2 ni retiro legacy: son entregas N5/N6/N8. No modifiques frontend, generes tipos de cliente ni ejecutes pruebas UI.

## Paradas obligatorias

- **D01/D02:** antes de publicar el comando, verificá ruta, DTO y fases aprobadas, cuándo hay resultado pendiente y qué intención habilita continuar. Si el contrato no resuelve un caso, proponé extensión y detené esa parte.
- **D06:** el piloto usa una fixture no adaptada explícita. No agregues omisión de draft ni atenuación por edad mientras la política siga diferida.
- **D05:** si aparece diferencia en duración/pools/pasivos, preservá el comportamiento comprobado y consultá antes de cambiarlo.
- **D08:** si recuperación/recompensa obliga a cambiar recibos, coordiná con N2. No resuelvas timeout creando otra clave ni cambiando a demo.
- Antes de modificar configuración local o usar un puerto ocupado, consultá o elegí un puerto libre sin tocar procesos ajenos. Ningún ensayo autoriza desplegar el piloto.

## Secuencia numerada

1. Definí fixtures en balance, mes 11, mes 12 y con posible colapso pasivo; cada una tiene corte/cartas y revisión inmutable conocidas. Llevalas al estado deseado sin ejecutar juego sobre DB compartida.
2. Adaptá `AVANZAR_MES` al coordinador aprobado: autorización, recibo, versión, fase y ausencia de resultado pendiente. Conservá historial, límite de meses, pasivos, colapso y draft; producí snapshot/recibo/consecuencias juntos.
3. Proyectá el contrato tipado completo: run/generación/versiones, fase/status, recursos, contenido permitido, resultado y comandos disponibles. GET no ejecuta negocio ni consulta catálogos admin para completar la respuesta.
4. Confirmá una sola versión de dominio y correlacionala con run/generación. Una respuesta o recibo antiguo conserva evidencia de su efecto, pero no reemplaza un snapshot más nuevo.
5. Ante timeout o commit incierto, permití recuperar/reintentar exactamente la misma clave, tipo, payload y versión esperada. Ausencia momentánea de recibo no habilita otra intención.
6. Entregá consecuencias antes/delta solicitado/delta aplicado/después y resultado neutral con texto. El cierre global y la recompensa se derivan del estado confirmado, no de cálculos del cliente.
7. Documentá en el paquete backend qué operaciones quedan legacy y qué garantías tiene el piloto, sin afirmar integración UI ni despliegue.

## Pruebas y criterios de aceptación

- [ ] Fixture con recurso 60 y efecto +10 termina en 70 una vez; reintento no lleva a 80.
- [ ] Recurso 95 con máximo 100 muestra delta solicitado +10 y aplicado +5; snapshot termina en 100.
- [ ] Condición incumplida no aplica efecto; resultado sin deltas sigue siendo legible.
- [ ] Mes 12 finaliza sin mes 13 ni pasivos de un siguiente mes inexistente.
- [ ] Colapso pasivo finaliza coherentemente y conserva obligación económica.
- [ ] Requests repetidos/concurrentes, recarga mediante GET, caída después de commit y conflicto no duplican mes ni efectos.
- [ ] Cambio de cuenta/run/generación y recibo tardío no contaminan otra sesión ni hacen retroceder el snapshot.
- [ ] Recorrido HTTP contra backend real aislado cubre éxito, conflicto, commit incierto y recuperación; los mocks no se presentan como E2E.
- [ ] Si necesitás Mongo, validá URI/hosts/base efectiva antes de conectar/índices, en instancia efímera dedicada.

## Entrega y traspaso

Entregá comando funcional en entorno aislado, evidencia HTTP, fixtures reproducibles y contratos consumidos. Detallá qué sigue legacy y qué depende de N5/N6/N7; no presentes el piloto como migración completa. Si falta Mongo real o una garantía previa, declará la aceptación pendiente y no cierres el alcance dependiente.
