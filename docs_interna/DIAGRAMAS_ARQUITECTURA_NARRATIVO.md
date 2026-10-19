# Arquitectura de Datos y Ciclo de Vida: Juego Narrativo (KingsCourt)

Este documento contiene la especificación técnica y los diagramas explicativos del **Juego Narrativo**, diseñados para que cualquier desarrollador de Backend o Frontend entienda:
1. **Cómo se relacionan las colecciones en MongoDB** mediante IDs, claves de recursos, tags y diccionarios de afinidad.
2. **Qué endpoints intervienen en el flujo de juego**, en qué orden se consumen y qué entidades leen o mutan en cada paso.

---

## 1. Diagrama de Entidades y Relaciones (Modelo Simplificado)

Para entender el modelo de datos rápidamente, el sistema se divide en **3 niveles simples**:
1. **Catálogo Base:** Todo el contenido del juego agrupado por `universo_id`.
2. **Selección Diaria (`daily_challenges`):** Los pools de IDs que se juegan en una fecha determinada.
3. **Partida Activa (`narrative_runs`):** El estado vivo del jugador y los IDs que tiene seleccionados en su turno.

### Diagrama de Relaciones e Identificadores

```mermaid
flowchart TD
    classDef univ fill:#EBF8FF,stroke:#2B6CB0,stroke-width:2px,color:#1A202C;
    classDef cat fill:#F7FAFC,stroke:#4A5568,stroke-width:1.5px,color:#1A202C;
    classDef daily fill:#FFFAF0,stroke:#C05621,stroke-width:2px,color:#1A202C;
    classDef run fill:#F0FFF4,stroke:#276749,stroke-width:2px,color:#1A202C;

    subgraph CATALOGO["1. Catálogo Base (El Universo y su Contenido)"]
        UNI["<b>narrative_universes</b><br/>PK: <code>_id</code> (ej: 'corte_medieval')"]:::univ
        PJ["<b>narrative_characters</b><br/>PK: <code>_id</code> (ej: 'pj_canciller')"]:::cat
        CARD["<b>narrative_cards</b><br/>PK: <code>_id</code> (ej: 'card_escudo')"]:::cat
        EVT["<b>narrative_events</b><br/>PK: <code>_id</code> (ej: 'evt_asedio')"]:::cat
        RES["<b>narrative_results</b><br/>PK: <code>_id</code> (ej: 'res_victoria')"]:::cat
        FIN["<b>narrative_finalizations</b> (Endings)<br/>PK: <code>_id</code> (ej: 'fin_derrota_oro')"]:::cat
    end

    subgraph CONFIG_DIA["2. Desafío Diario (Pools de la Fecha)"]
        DAILY["<b>daily_challenges</b><br/>PK: <code>game_id + date</code>"]:::daily
    end

    subgraph PARTIDA["3. Partida del Jugador (Runtime / Sesión)"]
        RUN["<b>narrative_runs</b><br/>PK: <code>user_id + date</code>"]:::run
    end

    %% Relaciones Catálogo
    UNI -->|"FK: universo_id"| PJ
    UNI -->|"FK: universo_id"| CARD
    UNI -->|"FK: universo_id"| EVT
    UNI -->|"FK: universo_id"| FIN
    EVT -->|"FK: opciones.resultado_id"| RES

    %% Relaciones Daily Challenge (Filtros del día)
    DAILY -->|"FK: config.universo_id"| UNI
    DAILY -->|"IDs ofrecidos: config.setup_corte_ofrecidos_ids"| PJ
    DAILY -->|"Mazo del mes: config.pool_cartas_mensuales_ids"| CARD
    DAILY -->|"Pool de eventos: config.pool_eventos_ids"| EVT

    %% Relaciones Partida Activa (Estado del jugador)
    RUN -->|"corte_ids & afinidad (IDs elegidos)"| PJ
    RUN -->|"cartas_en_mano (inventario)"| CARD
    RUN -->|"turno_actual.evento_actual_id"| EVT
    RUN -->|"turno_actual.resultado_obtenido_id"| RES
    RUN -.->|"Fin: recurso <= 0 o Mes 12 -> finalizacion_id"| FIN
```

> [!NOTE]
> **Conversaciones de corte (`narrative_conversations`):**
> Pertenecen a `universo_id` y se activan como evento incidental evaluando si los miembros de la corte coinciden con `requisitos[].personajeId`.

### Resumen de Claves de Unión (IDs clave)

* **`universo_id`**: Conecta todo el contenido base (personajes, cartas, eventos y endings) con su universo correspondiente.
* **`daily_challenges.config.*_ids`**: Listas de strings con los `_id` de personajes, cartas y eventos habilitados para ese día.
* **`narrative_runs.corte_ids`**: Array con los 2 `_id` de personajes elegidos para la partida.
* **`narrative_runs.cartas_en_mano`**: Array con los `_id` de cartas acumuladas en el inventario.
* **`narrative_runs.turno_actual.evento_actual_id`**: El `_id` del evento sorteado que el jugador debe resolver.
* **`narrative_events.opciones[].resultado_id`**: El `_id` del resultado que se aplica al elegir una opción.
* **`narrative_finalizations._id`**: El `_id` del ending (Victoria o Derrota por recurso) que se carga en la partida al finalizar.

---

## 2. Diagrama de Flujo de Endpoints V2 y Ciclo de Vida (Game Loop)

Este diagrama modela el viaje del usuario en el Frontend interactuando con los endpoints V2 ligeros del Backend ([`router_v2.py`](file:///c:/Users/nmonti/Desktop/proyectos/backend/mayores_actualizacionesSIPI-BACK/app/features/narrative/router_v2.py)).

```mermaid
sequenceDiagram
    autonumber
    actor Player as Jugador (Frontend UI)
    participant SetupEP as GET /partida/setup
    participant V2 as Endpoints V2 (/v2/partida/*)
    participant SupportEP as Endpoints de Consulta (/partida/*)
    participant DB as Base de Datos (MongoDB)

    %% FASE 0: SETUP
    Note over Player, DB: FASE PREVIA: Inicialización y Selección de Consejeros/Cartas
    Player->>SetupEP: GET /api/narrative/partida/setup?fecha=YYYY-MM-DD
    SetupEP->>DB: Lee daily_challenges, narrative_characters, narrative_cards
    SetupEP-->>Player: Devuelve setupCorte (3-4 opciones) y setupCartas (3-4 opciones)

    Player->>V2: POST /api/narrative/v2/partida/iniciar<br/>{ fecha, corteElegidaIds: [2], cartasElegidasIds: [2] }
    V2->>DB: Crea documento en narrative_runs (Mes 1, recursos iniciales, corte, cartas)<br/>Sortea 3 cartas de daily_challenges.pool_cartas_mensuales_ids
    V2-->>Player: 200 OK (fase="DRAFT_CARTA", cartasOfrecidas: [3 cartas])

    %% BUCLE MENSUAL (12 MESES)
    rect rgb(240, 248, 255)
        Note over Player, DB: BUCLE MENSUAL (Mes 1 al 12)
        
        %% Paso 1: Elegir carta
        Player->>V2: POST /api/narrative/v2/partida/elegir-carta-mes<br/>{ fecha, cartaElegidaId }
        V2->>DB: Agrega carta a run.cartas_en_mano y tags a run.tags_activos<br/>Sortea evento de pool_eventos_ids y evalúa visibilidad de opciones
        V2-->>Player: 200 OK (fase="EVENTO", eventoActual: { id, titulo, descripcion, opcionesVisibles: [...] })

        %% Paso 2: Decidir opción
        Player->>V2: POST /api/narrative/v2/partida/decidir-evento<br/>{ fecha, opcionId }
        V2->>DB: Lee narrative_results según peso de la opción elegida<br/>Aplica deltas a run.recursos y run.afinidad<br/>Evalúa derrota (recurso <= 0) o trigger de conversación incidental
        alt Hay derrota inmediata (recurso <= 0)
            V2-->>Player: 200 OK (fase="FIN", estado="DERROTA", finalizacion: {...})
        else Se activó conversación de corte
            V2-->>Player: 200 OK (fase="CONVERSACION", conversacionActual: { personajes, dialogos, decisiones: [...] })
            Player->>V2: POST /api/narrative/v2/partida/responder-conversacion<br/>{ fecha, decisionId }
            V2->>DB: Modifica run.afinidad según la decisión elegida
            V2-->>Player: 200 OK (fase="RESOLUCION", afinidadDeltas: {...})
        else Sin conversación
            V2-->>Player: 200 OK (fase="RESOLUCION", resultadoObtenido: {...}, deltas: {...})
        end

        %% Paso 3: Avanzar de mes
        Player->>V2: POST /api/narrative/v2/partida/avanzar-mes<br/>{ fecha }
        V2->>DB: Ejecuta efectos pasivos fin de mes de cartas en mano<br/>Incrementa run.mes_actual += 1
        alt mes_actual > 12 (Victoria)
            V2->>DB: Marca run.estado="VICTORIA", actualiza user_attempts
            V2-->>Player: 200 OK (fase="FIN", estado="VICTORIA", finalizacion: {...})
        else Siguiente mes (mes <= 12)
            V2->>DB: Sortea 3 cartas nuevas en run.turno_actual.cartas_ofrecidas_ids
            V2-->>Player: 200 OK (fase="DRAFT_CARTA", mesActual: N, cartasOfrecidas: [3 cartas])
        end
    end

    %% ENDPOINTS ON DEMAND
    Note over Player, DB: CONSULTAS ON-DEMAND / MODALES / RECUPERACIÓN F5
    Player->>V2: GET /api/narrative/v2/partida/estado?fecha=YYYY-MM-DD
    V2->>DB: Lee narrative_runs (turno_actual + estado)
    V2-->>Player: 200 OK (reconstruye UI en F5)

    Player->>SupportEP: GET /api/narrative/partida/corte?fecha=YYYY-MM-DD
    SupportEP->>DB: Lee personajes de la corte y afinidad actual
    SupportEP-->>Player: Modal de Consejeros y Afinidad

    Player->>SupportEP: GET /api/narrative/partida/inventario?fecha=YYYY-MM-DD
    SupportEP->>DB: Lee cartas en mano y tags activos
    SupportEP-->>Player: Modal de Inventario / Cartas activas
```

---

## 3. Resumen Rápido para Desarrolladores Frontend

### 1. ¿Cómo inicializar y renderizar el juego?
1. Llamar a `GET /api/narrative/partida/setup?fecha=YYYY-MM-DD`.
2. Si `estadoExistente` es nulo, mostrar la pantalla de selección con `setupCorte` y `setupCartas`.
3. Al confirmar la selección (2 personajes y 2 cartas), disparar `POST /api/narrative/v2/partida/iniciar`.

### 2. ¿Cómo manejar el Game Loop mensual?
El backend responde en cada turno con un `fase` que indica qué vista renderizar:
* `"DRAFT_CARTA"`: Mostrar las 3 cartas de `cartasOfrecidas`. Al seleccionar una, llamar a `POST /api/narrative/v2/partida/elegir-carta-mes`.
* `"EVENTO"`: Mostrar `eventoActual` con sus `opcionesVisibles`. Al pulsar una opción, llamar a `POST /api/narrative/v2/partida/decidir-evento`.
* `"CONVERSACION"`: (Si ocurrió un dilema entre consejeros). Mostrar el diálogo y las opciones. Al elegir, llamar a `POST /api/narrative/v2/partida/responder-conversacion`.
* `"RESOLUCION"`: Mostrar el resultado del mes y los deltas obtenidos. Botón "Continuar al siguiente mes" llama a `POST /api/narrative/v2/partida/avanzar-mes`.
* `"FIN"`: Mostrar pantalla final con la victoria o derrota provista en `finalizacion`.

### 3. ¿Qué hacer en caso de recarga (F5)?
Llamar a `GET /api/narrative/v2/partida/estado?fecha=YYYY-MM-DD`. El backend devolverá el `NarrativeTurnoDeltaResponse` exacto del momento en que se quedó la partida, permitiendo restaurar la UI sin pérdida de datos.
