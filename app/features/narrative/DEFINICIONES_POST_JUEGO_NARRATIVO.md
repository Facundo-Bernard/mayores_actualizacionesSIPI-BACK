# Especificación de Endpoints POST · Motor Narrativo Roguelite

Guía técnica para desarrolladores con las definiciones de campos, reglas de negocio y payloads JSON exactos requeridos por cada endpoint `POST` del sistema (tanto de la **Torre de Control / Administración** como del **Ciclo de Partida del Alumno**).

---

## 📌 Configuración y Headers Globales

- **Base URL (Local):** `http://localhost:8080`
- **Prefijo API:** `/api/narrative`
- **Headers Obligatorios:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <JWT_TOKEN>
  ```
- **Claves Primarias:** Se utiliza el campo `_id` (también aceptado como `id` por Pydantic).
- **Rangos de Afinidad y Recursos:** Escala `0` a `100` (el valor inicial estándar es `50`).

---

## 📑 Catálogo de Enums y Valores Permitidos

Antes de armar los payloads, ten en cuenta los valores restringidos aceptados por el backend:

| Enum | Valores Permitidos | Descripción |
|---|---|---|
| **`disparador`** | `"al_obtener"`, `"cada_mes"`, `"en_evento_positivo"`, `"en_evento_negativo"`, `"al_final_partida"` | Momento en el que se evalúa o ejecuta la regla ECA. |
| **`operador`** | `">="`, `"<="`, `">"`, `"<"`, `"=="`, `"!="` | Comparador lógico para condiciones. |
| **`tipo_condicion`** | `"comparar_recurso"`, `"tiene_personaje"`, `"afinidad_personaje"`, `"tiene_tag"`, `"tiene_carta"` | Qué verifica la condición. |
| **`tipo_accion`** | `"modificar_recurso"`, `"modificar_afinidad"`, `"otorgar_tag"`, `"amortiguar_danio"` | Acción que ejecuta el efecto al cumplirse las condiciones. |
| **`tipo_calculo`** | `"fijo"`, `"porcentual"` | Si el `valor` suma/resta directo (+10, -5) o porcentaje (+15%). |
| **`categoria_carta`**| `"item"`, `"bonus"`, `"personaje"` | Clasificación de cartas de apoyo en el inventario. |
| **`tipo_resultado`** | `"positivo"`, `"negativo"`, `"neutro"` | Clasificación visual y temática del desenlace del evento. |

---

## 🧩 Patrón ECA (Event - Condition - Action) Reutilizable

Varios objetos (`personajes`, `cartas`, `resultados`, `eventos`) utilizan este bloque para sus efectos pasivos:

```json
{
  "disparador": "cada_mes",
  "condiciones": [
    {
      "tipo": "comparar_recurso",
      "clave": "oro",
      "operador": ">=",
      "valor": 50,
      "personaje_id": null,
      "carta_id": null,
      "tag": null
    }
  ],
  "accion": {
    "tipo": "modificar_recurso",
    "clave": "moral",
    "tipo_calculo": "fijo",
    "valor": 5.0,
    "personaje_id": null,
    "tag": null
  }
}
```

---

# 👑 1. Endpoints de Administración (Torre de Control)

---

### 1.1. Universos Temáticos
- **Endpoint:** `POST /api/narrative/admin/universos`
- **Descripción:** Crea o actualiza un universo narrativo definiendo los recursos vitales que gestionará el jugador.

#### Campos Requeridos:
- `_id` *(string, requerido)*: Identificador único (ej: `"corte_medieval"`).
- `nombre` *(string, requerido)*: Nombre visible.
- `descripcion` *(string, requerido)*: Descripción temática.
- `icono` *(string, opcional, default: `"crown"`)*: Identificador de ícono.
- `recursos` *(array, requerido)*: Lista de recursos del reino (`clave`, `nombre`, `icono`, `min`, `max`, `inicial`).

#### Payload JSON:
```json
{
  "_id": "corte_medieval",
  "nombre": "Crónicas de la Corte Real",
  "descripcion": "Gobierna un reino feudal al borde de la rebelión y el invierno perpetuo.",
  "icono": "crown",
  "recursos": [
    {
      "clave": "oro",
      "nombre": "Tesoro Real",
      "icono": "coins",
      "min": 0,
      "max": 100,
      "inicial": 50
    },
    {
      "clave": "comida",
      "nombre": "Graneros del Valle",
      "icono": "wheat",
      "min": 0,
      "max": 100,
      "inicial": 50
    },
    {
      "clave": "orden",
      "nombre": "Paz y Guardia Civil",
      "icono": "shield",
      "min": 0,
      "max": 100,
      "inicial": 50
    },
    {
      "clave": "moral",
      "nombre": "Aprobación del Pueblo",
      "icono": "heart",
      "min": 0,
      "max": 100,
      "inicial": 50
    }
  ]
}
```

---

### 1.2. Personajes de Corte
- **Endpoint:** `POST /api/narrative/admin/personajes`
- **Descripción:** Crea o actualiza un consejero reclutable para la corte activa del jugador.

#### Campos Requeridos:
- `_id` *(string, requerido)*: ID único (ej: `"pj_canciller_elena"`).
- `universo_id` *(string, requerido)*: Universo temático al que pertenece.
- `nombre` *(string, requerido)*: Nombre de pila.
- `titulo` *(string, requerido)*: Título o cargo nobiliario.
- `imagen` *(string, requerido)*: Ruta o URL del retrato.
- `descripcion` *(string, requerido)*: Biografía y motivaciones.
- `pros` *(array de strings, opcional)*: Ventajas informativas.
- `cons` *(array de strings, opcional)*: Desventajas informativas.
- `tags` *(array de strings, opcional)*: Tags pasivos del personaje.
- `afinidad_inicial` *(int, opcional, default: `50`)*: Afinidad con la corona (0 a 100).
- `efectos` *(array de reglas ECA, opcional)*: Pasivas que aporta al estar en corte.
- `conversaciones` *(array de objetos, opcional)*: Probabilidad de disparar diálogos.

#### Payload JSON:
```json
{
  "_id": "pj_canciller_elena",
  "universo_id": "corte_medieval",
  "nombre": "Elena",
  "titulo": "Canciller de la Moneda",
  "imagen": "/assets/narrative/characters/canciller.webp",
  "descripcion": "Diplomática calculadora. Protege las arcas reales con mano firme frente a las exigencias militares.",
  "pros": [
    "Genera +10 de oro en balance mensual",
    "Reduce costos de sobornos y tratados"
  ],
  "cons": [
    "-5 de moral popular si el tesoro supera 80 puntos"
  ],
  "tags": [
    "finanzas",
    "diplomacia",
    "noble"
  ],
  "afinidad_inicial": 50,
  "efectos": [
    {
      "disparador": "cada_mes",
      "condiciones": [],
      "accion": {
        "tipo": "modificar_recurso",
        "clave": "oro",
        "tipo_calculo": "fijo",
        "valor": 10.0,
        "personaje_id": null,
        "tag": null
      }
    }
  ],
  "conversaciones": [
    {
      "idConversacion": "conv_disputa_tesoro_militar",
      "probabilidad": 0.35
    }
  ]
}
```

---

### 1.3. Cartas de Apoyo
- **Endpoint:** `POST /api/narrative/admin/cartas`
- **Descripción:** Crea o actualiza cartas de inventario que el jugador elige en la preparación o en los drafts mensuales.

#### Campos Requeridos:
- `_id` *(string, requerido)*: ID único (ej: `"carta_sello_real"`).
- `universo_id` *(string, requerido)*: ID del universo.
- `categoria` *(string, requerido)*: `"item"`, `"bonus"` o `"personaje"`.
- `nombre` *(string, requerido)*: Título de la carta.
- `descripcion` *(string, requerido)*: Efecto narrativo y mecánico.
- `imagen` *(string, requerido)*: Arte de la carta.
- `tags` *(array de strings, opcional)*: Tags que activa en el reino (ej: `["sello_real"]`).
- `efectos` *(array de reglas ECA, opcional)*: Efectos inmediatos (`al_obtener`) o mensuales (`cada_mes`).

#### Payload JSON:
```json
{
  "_id": "carta_sello_real",
  "universo_id": "corte_medieval",
  "categoria": "item",
  "nombre": "Sello Real de Cera",
  "descripcion": "Autoriza decretos de emergencia y desbloquea opciones secretas en eventos de crisis.",
  "imagen": "/assets/narrative/cards/sello_real.webp",
  "tags": [
    "sello_real",
    "legitimidad"
  ],
  "efectos": [
    {
      "disparador": "al_obtener",
      "condiciones": [],
      "accion": {
        "tipo": "otorgar_tag",
        "clave": null,
        "tipo_calculo": "fijo",
        "valor": 0.0,
        "personaje_id": null,
        "tag": "sello_real"
      }
    }
  ]
}
```

---

### 1.4. Desenlaces / Consecuencias
- **Endpoint:** `POST /api/narrative/admin/resultados`
- **Descripción:** Consecuencia o desenlace de una opción de evento con deltas numéricos sobre recursos y afinidad.

#### Campos Requeridos:
- `_id` *(string, requerido)*: ID único (ej: `"res_suministros_asegurados"`).
- `universo_id` *(string, requerido)*: ID del universo.
- `titulo` *(string, requerido)*: Nombre del desenlace.
- `texto` *(string, requerido)*: Conclusión narrativa.
- `imagen` *(string, requerido)*: Ilustración del resultado.
- `tipo_resultado` *(string, opcional, default: `"neutro"`)*: `"positivo"`, `"negativo"` o `"neutro"`.
- `efectos` *(array de reglas ECA, opcional)*: Recursos modificados con disparador `"al_obtener"`.
- `impacto_afinidad` *(array de objetos, opcional)*: Lista con `personaje_id` y `delta` (+15, -10).

#### Payload JSON:
```json
{
  "_id": "res_suministros_asegurados",
  "universo_id": "corte_medieval",
  "titulo": "Suministros Asegurados",
  "texto": "La oportuna compra de grano evitó la hambruna generalizada en el valle y calmó los ánimos en la capital.",
  "imagen": "/assets/narrative/results/suministros.webp",
  "tipo_resultado": "positivo",
  "efectos": [
    {
      "disparador": "al_obtener",
      "condiciones": [],
      "accion": {
        "tipo": "modificar_recurso",
        "clave": "comida",
        "tipo_calculo": "fijo",
        "valor": 25.0,
        "personaje_id": null,
        "tag": null
      }
    },
    {
      "disparador": "al_obtener",
      "condiciones": [],
      "accion": {
        "tipo": "modificar_recurso",
        "clave": "oro",
        "tipo_calculo": "fijo",
        "valor": -15.0,
        "personaje_id": null,
        "tag": null
      }
    }
  ],
  "impacto_afinidad": [
    {
      "personaje_id": "pj_canciller_elena",
      "delta": 10
    }
  ]
}
```

---

### 1.5. Eventos Mensuales
- **Endpoint:** `POST /api/narrative/admin/eventos`
- **Descripción:** Evento dilemático mensual con opciones A, B y Secretas, desenlaces ponderados y modificadores de probabilidad condicionales.

#### Campos Requeridos:
- `_id` *(string, requerido)*: ID único (ej: `"evt_helada_cosechas"`).
- `universo_id` *(string, requerido)*: ID del universo.
- `titulo` *(string, requerido)*: Título del evento.
- `descripcion` *(string, requerido)*: Dilema que enfrenta el monarca.
- `imagen` *(string, requerido)*: Fondo ilustrativo.
- `tags_tematicos` *(array de strings, opcional)*: Categorías (ej: `["clima", "comida"]`).
- `peso_base` *(float, opcional, default: `100.0`)*: Probabilidad relativa de sorteo.
- `opciones` *(array, requerido)*: Lista de opciones:
  - `id`: `"op_a"`, `"op_b"`, `"op_c"`.
  - `texto`: Texto visible en la carta de decisión.
  - `es_secreta`: `true` | `false`.
  - `condiciones`: Requisito para desbloquearla si es secreta.
  - `resultados_posibles`: Lista de resultados con `resultado_id`, `peso_base` y `modificadores_probabilidad`.

#### Payload JSON:
```json
{
  "_id": "evt_helada_cosechas",
  "universo_id": "corte_medieval",
  "titulo": "La Gran Helada en el Valle",
  "descripcion": "Una ola de frío polar congeló los campos de trigo. Los silos campesinos amenazan con quedar vacíos.",
  "imagen": "/assets/narrative/events/helada.webp",
  "tags_tematicos": [
    "clima",
    "comida",
    "crisis",
    "pueblo"
  ],
  "peso_base": 100.0,
  "opciones": [
    {
      "id": "op_a",
      "texto": "Enviar patrullas a custodiar y racionar graneros",
      "es_secreta": false,
      "condiciones": [],
      "resultados_posibles": [
        {
          "resultado_id": "res_suministros_asegurados",
          "peso_base": 50.0,
          "modificadores_probabilidad": [
            {
              "condicion": {
                "tipo": "tiene_personaje",
                "clave": null,
                "operador": null,
                "valor": null,
                "personaje_id": "pj_comandante_marcus",
                "carta_id": null,
                "tag": null
              },
              "delta_peso": 35.0,
              "explicacion": "+35% por liderazgo del Comandante Marcus"
            }
          ]
        },
        {
          "resultado_id": "res_emboscada_y_perdida",
          "peso_base": 50.0,
          "modificadores_probabilidad": []
        }
      ]
    },
    {
      "id": "op_b",
      "texto": "Comprar grano de emergencia a mercaderes extranjeros",
      "es_secreta": false,
      "condiciones": [],
      "resultados_posibles": [
        {
          "resultado_id": "res_suministros_asegurados",
          "peso_base": 60.0,
          "modificadores_probabilidad": []
        }
      ]
    },
    {
      "id": "op_c",
      "texto": "[Secreto] Decretar requisa general amparado en el Sello Real",
      "es_secreta": true,
      "condiciones": [
        {
          "tipo": "tiene_tag",
          "clave": null,
          "operador": null,
          "valor": null,
          "personaje_id": null,
          "carta_id": null,
          "tag": "sello_real"
        }
      ],
      "resultados_posibles": [
        {
          "resultado_id": "res_suministros_asegurados",
          "peso_base": 100.0,
          "modificadores_probabilidad": []
        }
      ]
    }
  ]
}
```

---

### 1.6. Diálogos de Corte
- **Endpoint:** `POST /api/narrative/admin/conversaciones`
- **Descripción:** Disputa entre 2 miembros de la corte activa con frases alternadas y decisiones de mediación monárquica.

#### Campos Requeridos:
- `_id` *(string, requerido)*: ID único (ej: `"conv_disputa_tesoro_militar"`).
- `universo_id` *(string, requerido)*: ID del universo.
- `titulo` *(string, requerido)*: Nombre de la situación.
- `imagen` *(string, requerido)*: Fondo ilustrativo de la sala o pasillo.
- `requisitos` *(array, requerido)*: Exactamente los 2 personajes requeridos (`[{ "personajeId": "..." }]`).
- `frases` *(array, requerido)*: Guion de frases (`personajeId`, `texto`).
- `decisiones` *(array, requerido)*: Opciones de respuesta del monarca (`opcion`, `texto`, `resultado_texto`, `impacto_afinidad`).

#### Payload JSON:
```json
{
  "_id": "conv_disputa_tesoro_militar",
  "universo_id": "corte_medieval",
  "titulo": "Presupuesto de Campaña Militar",
  "imagen": "/assets/narrative/conversations/sala_reuniones.webp",
  "requisitos": [
    { "personajeId": "pj_canciller_elena" },
    { "personajeId": "pj_comandante_marcus" }
  ],
  "frases": [
    {
      "personajeId": "pj_comandante_marcus",
      "texto": "Mis hombres necesitan mejores armaduras y raciones si queremos mantener segura la frontera norte."
    },
    {
      "personajeId": "pj_canciller_elena",
      "texto": "Si desviamos más oro a la guarnición, asfixiaremos el comercio y los gremios se rebelarán."
    }
  ],
  "decisiones": [
    {
      "opcion": 1,
      "texto": "Respaldar a Elena: la prudencia fiscal es prioridad ante el invierno",
      "condiciones": [],
      "resultado_texto": "Marcus aprieta la mandíbula y acata la orden con evidente desagrado.",
      "impacto_afinidad": [
        { "personaje_id": "pj_canciller_elena", "delta": 15 },
        { "personaje_id": "pj_comandante_marcus", "delta": -15 }
      ]
    },
    {
      "opcion": 2,
      "texto": "Respaldar a Marcus: las murallas y las armas deben garantizar la paz",
      "condiciones": [],
      "resultado_texto": "Elena toma notas en silencio, advirtiendo que los balances estarán al límite.",
      "impacto_afinidad": [
        { "personaje_id": "pj_canciller_elena", "delta": -15 },
        { "personaje_id": "pj_comandante_marcus", "delta": 15 }
      ]
    }
  ]
}
```

---

### 1.7. Generador de Desafíos Mensuales
- **Endpoint:** `POST /api/narrative/admin/generar-mes?year=2026&month=1&universo_id=corte_medieval`
- **Descripción:** Genera automáticamente los 28 a 31 desafíos diarios del mes en la colección `daily_challenges` (con `game_id: "narrativo"`).
- **Parámetros Query:**
  - `year`: Año (`2020` a `2050`).
  - `month`: Mes (`1` a `12`).
  - `universo_id`: ID del universo temático (ej: `"corte_medieval"`).
- **Cuerpo (Body):** No requiere body (`null`).
- **Respuesta JSON:**
```json
{
  "year": 2026,
  "month": 1,
  "universo_id": "corte_medieval",
  "desafios_creados": 31
}
```

---

# 🎮 2. Endpoints de Partida / Runtime del Alumno

Los endpoints del ciclo de juego responden siempre con el **`EstadoPartidaActivaResponse`** completo (recursos actuales, mes actual, fase actual, personajes en corte, cartas en mano, etc.).

---

### 2.1. Iniciar Partida (Fase 0 - Setup)
- **Endpoint:** `POST /api/narrative/partida/iniciar`
- **Descripción:** El alumno elige 2 personajes de los 5 ofrecidos y 2 cartas de las 5 ofrecidas para arrancar el año.
```json
{
  "date": "2026-10-15",
  "corte_elegida_ids": [
    "pj_canciller_elena",
    "pj_comandante_marcus"
  ],
  "cartas_iniciales_ids": [
    "carta_sello_real",
    "carta_veteranos"
  ]
}
```

---

### 2.2. Elegir Carta del Mes (Fase 1 - Draft)
- **Endpoint:** `POST /api/narrative/partida/elegir-carta-mes`
- **Descripción:** Elige 1 de las 3 cartas sorteadas del mes. El backend la agrega al inventario, aplica sus efectos y sortea inmediatamente el evento del mes (pasando a Fase 2).
```json
{
  "date": "2026-10-15",
  "carta_id": "carta_veteranos"
}
```

---

### 2.3. Decidir Evento (Fase 2 - Dilema)
- **Endpoint:** `POST /api/narrative/partida/decidir-evento`
- **Descripción:** El alumno elige una opción (`"op_a"`, `"op_b"` u `"op_c"`). El motor computa probabilidades con modificadores pasivos, sortea el desenlace, aplica deltas de recursos y determina si se dispara un diálogo en Fase 3.
```json
{
  "date": "2026-10-15",
  "opcion_id": "op_a"
}
```

---

### 2.4. Responder Diálogo de Corte (Fase 3 - Intervención)
- **Endpoint:** `POST /api/narrative/partida/responder-conversacion`
- **Descripción:** El alumno elige la opción de mediación (1, 2 o 3). Se aplican los deltas de afinidad sobre los dos cortesanos y se pasa a Fase 4 (Balance).
```json
{
  "date": "2026-10-15",
  "opcion_numero": 1
}
```

---

### 2.5. Avanzar Mes (Fase 4 - Balance Mensual)
- **Endpoint:** `POST /api/narrative/partida/avanzar-mes`
- **Descripción:** Cierra el balance del mes, guarda el snapshot en `historial_mensual`, ejecuta pasivas `cada_mes`, y sortea 3 cartas nuevas para el siguiente mes (o emite el epílogo final y puntuación de rango S/A/B/C si era el Mes 12).
```json
{
  "date": "2026-10-15"
}
```

---

### 2.6. Reiniciar Partida
- **Endpoint:** `POST /api/narrative/partida/reiniciar`
- **Descripción:** Elimina la partida viva del alumno para la fecha dada y le permite volver a comenzar el desafío diario desde la Fase 0 (Draft de Setup).
```json
{
  "date": "2026-10-15"
}
```
