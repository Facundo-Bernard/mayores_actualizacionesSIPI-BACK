# N3 — Contenido inmutable y reglas ejecutables

## Rol y misión

Actuá como responsable de contenido narrativo y semántica ECA. Al ejecutar esta etapa, impedir que editar el catálogo cambie una partida nueva ya iniciada y asegurar que todo contenido publicable sea estructural y semánticamente ejecutable. Reutilizar el validador y los motores existentes; no diseñar un lenguaje de reglas nuevo.

Leer la [guía común](00-guia-de-ejecucion.md), la entrega de [N0](N0-bases-contrato-y-caracterizacion.md) y E07/E08/E14/E15 y N3 de la [auditoría](../refactor/06-auditoria-arquitectura-y-plan-narrativo.md). Coordinar referencias de contenido con [N2](N2-comandos-recibos-y-economia.md); N3 puede avanzar en paralelo con extracción interna de N1 si no se editan los mismos módulos.

## Contexto y puntos de entrada

En el corte auditado se releían catálogos vivos y el admin reemplazaba documentos por ID. La generación mensual y la carga manual de finales también podían reemplazar datos; proteger solo CRUD es insuficiente. Fijar únicamente el grafo tampoco fija cartas, recursos, pasivas, pools ni finales.

ECA ejecutaba modificación de recursos, afinidad y otorgamiento de tags. Que exista un enum de `amortiguar_danio` no demuestra un handler. Los esquemas tipados rechazan ciertos desconocidos, pero el validador de payload inline y las restricciones semánticas eran incompletos. Los pesos no finitos podían atravesar la validación. Verificar el estado real antes de corregir.

Fuentes B:

- `app/features/narrative/validation/graph_validator.py` y `schemas/rules_schemas.py`, `schemas/catalog_schemas.py` dentro de la misma feature.
- `app/features/narrative/engine/rule_engine.py`, `engine/event_director.py`, `game/motor_v2/graph_engine.py`.
- `app/features/narrative/admin/crud_service.py`, `admin/challenge_service.py`, `admin/router.py`, `admin/rules_catalog.py`.
- `app/features/narrative/game/universe_resources.py`, `setup_service.py`, `transition_service.py` y selectores de los motores.
- F: `admin_src/` solo para localizar consumidores concretos de validación/publicación; no rediseñar el visor de grafos.

## Dependencias, alcance y exclusiones

Exigir contrato/aislamiento N0. Acordar con N2 identificadores y referencias inmutables antes de conectar runs al catálogo nuevo. No migrar catálogo compartido ni runs históricos durante esta etapa; preparar fixtures y ensayos aislados.

No agregar acciones hipotéticas ni cambiar balance. Un reporte HTTP 200 con errores de validación puede ser correcto: distinguir el contrato de diagnóstico del rechazo de publicación. La revisión histórica limitada a 500 documentos por tipo no acredita que todo un catálogo fue validado.

## Paradas obligatorias

- **D09:** antes de diseñar publicación, preguntar cómo se aprueba una revisión, qué ocurre con contenido inválido existente y cómo se conservan revisiones referenciadas. No bloquear ediciones legacy ni borrar datos silenciosamente.
- **D04:** antes de unificar motores, acordar recursos/personajes ausentes, copias/instancias, orden y redondeo. Explicar dónde divergen hoy; no cambiar `round` por otro redondeo bajo el nombre de refactor.
- **D05:** antes de corregir pesos mostrados/sorteados o alterar selección, aprobar la política; preservar pools y doce meses salvo decisión explícita. No importar el 50%/75% de la demo.
- **D08:** antes de elegir almacenamiento de revisiones y recibos, coordinar límites y atomicidad. No duplicar indefinidamente catálogos en cada recibo sin medir tamaño.
- **D06:** si aparecen acciones adaptadas por edad, dejar pendiente su semántica hasta aprobar política de dominio; conservar ajustes meramente visuales.
- Inspeccionar datos reales requiere entorno/dataset de lectura autorizado; nunca ejecutar seeds para completar un inventario.

## Secuencia de implementación

1. Inventariar capacidades declaradas, handlers reales y uso en fixtures/contenido autorizado. Clasificar soportado, enum sin ejecución, desconocido y semántica ambigua. Cubrir acciones, triggers, operadores, referencias y restricciones de universo.
2. Validar forma y tipos del payload antes de recorrer nodos/opciones; rechazar pesos no finitos y referencias inválidas con diagnóstico controlado, no `TypeError`. Exigir campos por discriminador ECA, motor permitido y mínimos/máximos coherentes. Paginar inventario completo o declarar límites explícitos.
3. Tras D09, establecer revisión inmutable de universo, recursos, desafío/pools, corte, cartas, eventos/resultados, conversaciones, grafos y finales. Identificar reglas ejecutadas por una versión compatible; un identificador decorativo sin resolución estable no fija reglas.
4. Pasar todas las lecturas del protocolo nuevo por esas referencias. Incluir revisión en cachés y no devolver objetos mutables compartidos que permitan alterar una partida fijada. Probar edición y borrado del catálogo de autoría mientras continúa el run.
5. Adaptar publicación en CRUD, generación mensual y cargas manuales. Los cambios crean otra revisión; las referenciadas siguen disponibles. Validación obligatoria antes de habilitar contenido nuevo, sin rediseñar todo el admin.
6. Tras D04/D05, fijar orden de fuentes/instancias y operaciones con resultados deterministas. Reutilizar semántica donde sea equivalente, conservando diferencias aprobadas de V1/V2. Implementar solo capacidades requeridas y aprobadas; rechazar publicación de las no ejecutables con error explicativo.
7. Capturar consecuencias ordenadas al ejecutar: ID estable, origen, antes, delta solicitado/aplicado y después. Tags e inventario tienen consecuencias tipadas; efectos netos cero no justifican borrar texto narrativo ni perder trazabilidad de efectos individuales.

## Pruebas y aceptación

- [ ] Raíz lista, estructuras malformadas, enums desconocidos, campos semánticos ausentes y `NaN`/infinito producen diagnósticos controlados.
- [ ] No se publica una acción sin handler ni referencias de otro universo no permitidas.
- [ ] Editar catálogo, regenerar desafío o cargar finales no cambia un run fijado.
- [ ] Borrar una edición no borra revisiones usadas por runs activos.
- [ ] Orden, porcentajes, clamps y redondeos positivos/negativos tienen expectativas aprobadas.
- [ ] Consecuencias conservan valores reales, multiplicidad acordada y resultados neutrales.
- [ ] Los consumidores admin mantienen su contrato o cuentan con migración aprobada y prueba en navegador.

## Entrega y traspaso

Entregar catálogo de capacidades, política aprobada de publicación, inventario de vías de escritura, referencias de revisión y pruebas de inmutabilidad. Identificar contenido incompatible sin repararlo silenciosamente. N4 debe poder usar una fixture fijada y N8 debe conocer los requisitos de migración; no aplicar esos cambios a producción desde N3.
