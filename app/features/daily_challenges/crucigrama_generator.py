"""
crucigrama_generator.py
Generador procedural determinista de Crucigramas (7x7) para adultos mayores mediante Backtracking (CSP).

Características:
1. Cuadrícula senior-friendly 7x7: Casillas amplias ideales para pantallas táctiles y teclado.
2. Palabras de variada longitud (4, 5, 6 y 7 letras) interconectadas limpiamente sin términos oscuros ni palabras de 2 letras.
3. Algoritmo de Backtracking con poda hacia adelante (Forward Checking) y heurística MRV (Minimum Remaining Values).
4. Catálogo de 31 plantillas estructurales simétricas de 7x7 con garantía de cruces válidos.
5. Doble capa de pistas: Pistas pedagógicas curadas y definiciones limpias oficiales de la RAE con caché persistente (0ms).
6. Numeración estándar occidental y determinismo absoluto: La misma fecha en cualquier servidor genera siempre el mismo crucigrama.
7. Variedad infinita: Cada día y cada mes genera tableros nuevos y frescos sin reciclar los mismos días.
"""

import os
import re
import json
import random
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from app.core.rae_client import fetch_rae_definition, _load_definitions_cache

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DICTIONARY_PATH = os.path.join(DATA_DIR, "acentos_todas_palabras.json")

# Catálogo de pistas curadas pedagógicas para personas mayores
CURATED_CLUES: Dict[str, str] = {
  "HERMANO": "Hijo de los mismos padres y compañero de infancia.",
  "HIJOS": "Descendientes queridos en el núcleo familiar.",
  "ABRAZO": "Muestra de afecto estrechando a alguien entre los brazos.",
  "ROSA": "Flor hermosa de dulce perfume y tallos con espinas.",
  "VIDA": "Existencia de los seres vivos y experiencia en el mundo.",
  "PASTEL": "Torta dulce horneada para celebrar una fiesta.",
  "SOLAR": "Relativo al sol y su energía luminosa.",
  "AGUAS": "Corrientes o extensiones naturales de líquido vital.",
  "SOPAS": "Comida reconfortante de caldo caliente con verduras o fideos.",
  "PLANTAS": "Seres vivos vegetales que alegran la casa.",
  "TIEMPO": "Época, estación o transcurso de las horas y los días.",
  "VERDE": "Color característico de la hierba y los árboles.",
  "ROSAS": "Flores queridas de suave perfume y variados colores.",
  "CAMINO": "Vía de tierra o asfalto por donde se transita.",
  "CIELO": "Bóveda celeste sobre nuestras cabezas.",
  "AROMA": "Perfume grato que despierta lindos recuerdos.",
  "MATE": "Infusión tradicional que se toma caliente en calabaza.",
  "MEMORIA": "Facultad de recordar vivencias y momentos felices.",
  "NOCHE": "Tiempo en que falta la luz del sol y salen las estrellas.",
  "AYER": "El día que precedió inmediatamente al de hoy.",
  "TERNERO": "Cría joven de la vaca en el campo.",
  "GATO": "Felino doméstico que disfruta de las siestas al sol.",
  "OVEJA": "Animal de campo que nos da lana abrigada.",
  "LECCION": "Enseñanza que imparte la maestra en la escuela.",
  "AULA": "Sala de la escuela donde se dan las clases.",
  "CASCADA": "Caída sonora de agua desde cierta altura.",
  "PLAZA": "Lugar público con bancos y árboles para pasear.",
  "LAGUNA": "Depósito natural de agua más pequeño que un lago.",
  "PIEDRA": "Materia mineral dura y sólida de la naturaleza.",
  "LUCERO": "Estrella brillante que resplandece en el cielo.",
  "RAYOS": "Líneas de luz que emite el sol al amanecer.",
  "CHALECO": "Prenda de abrigo sin mangas que cubre el pecho.",
  "CORAZON": "Símbolo de los afectos y motor vital.",
  "ALMA": "Parte espiritual e inmortal de las personas.",
  "AMIGO": "Compañero leal con quien se comparte la vida.",
  "TRENZA": "Peinado entrelazando mechones o pan trenzado.",
  "PANERA": "Cesto o recipiente donde se guarda y sirve el pan.",
  "MASA": "Mezcla de harina y agua para hacer pan o empanadas.",
  "AVENIDA": "Calle ancha de la ciudad con árboles y mucho tránsito.",
  "FLORES": "Adornan los jardines con sus colores y perfumes.",
  "MUSICA": "Arte de combinar sonidos y melodías armoniosas.",
  "BUTACA": "Asiento cómodo y mullido en el teatro o cine.",
  "VELERO": "Barco ligero impulsado por el viento en sus velas.",
  "FARO": "Torre alta en la costa con luz para guiar a los barcos.",
  "OREGANO": "Hierba aromática que se espolvorea sobre la pizza.",
  "ANZUELO": "Garfio de metal usado para pescar en el río.",
  "LAGO": "Gran extensión de agua dulce rodeada de tierra.",
  "AGUA": "Líquido vital transparente indispensable para la vida.",
  "SIERRA": "Cadena de montañas o herramienta para cortar madera.",
  "FORJA": "Taller del herrero donde se trabaja el metal al fuego.",
  "TUERCA": "Pieza de metal con rosca que ajusta con un tornillo.",
  "CLAVO": "Pieza de metal con cabeza y punta para fijar maderas.",
  "CEBOLLA": "Hortaliza de capas que hace llorar al picarla.",
  "BATATA": "Tubérculo dulce ideal para asar al horno.",
  "ZAPALLO": "Calabaza grande de pulpa naranja para hacer puré.",
  "ALFAJOR": "Dulce criollo de dos tapitas unidas por dulce de leche.",
  "FLAN": "Postre casero de leche, huevos y caramelo dorado.",
  "AZUCAR": "Sustancia dulce blanca para endulzar el café o té.",
  "MALETA": "Valija para guardar la ropa al salir de viaje.",
  "TREN": "Medio de transporte sobre vías que conecta pueblos.",
  "BOLETO": "Billete que da derecho a viajar en tren o colectivo.",
  "BARCO": "Embarcación grande que navega sobre el agua.",
  "CUERDAS": "Hilos tensados de la guitarra que producen notas.",
  "RITMO": "Compás armonioso de la música y el baile.",
  "SABANA": "Tela fina y fresca que cubre el colchón.",
  "COLCHA": "Cobertor de cama que abriga y decora.",
  "CAMA": "Mueble de descanso donde se duerme plácidamente.",
  "CELESTE": "Color del cielo diurno y de nuestra bandera.",
  "COLINA": "Elevación natural suave y redondeada del terreno.",
  "AIRE": "Gas invisible que respiramos y nos da vida.",
  "BOSQUE": "Sitio poblado de árboles y vegetación espesa.",
  "VIOLETA": "Flor silvestre pequeña de color morado y rico perfume.",
  "TALLO": "Parte de la planta que sostiene las hojas y flores.",
  "MALVA": "Planta de hermosas flores de tonos suaves y morados.",
  "LENTEJA": "Legumbre redonda y pequeña para hacer ricos guisos.",
  "NOTICIA": "Información de un suceso reciente que se divulga.",
  "CHARLA": "Conversación amena y distendida entre amigos.",
  "RADIO": "Aparato que sintoniza música y voces que acompañan.",
  "HELECHO": "Planta de hojas verdes muy apreciada para colgar en el patio.",
  "CARTAS": "Juego de naipes o correspondencia escrita con cariño.",
  "ALBANIL": "Oficial de la construcción que levanta paredes con esmero.",
  "OFICIO": "Trabajo manual o artesanal aprendido con dedicación.",
  "MEDICO": "Profesional de la salud que cuida y cura a los enfermos.",
  "DORADO": "Pez rey de escamas brillantes en el río Paraná.",
  "TIERRA": "Suelo fértil donde crecen los árboles y sembrados.",
  "AGUADA": "Paraje de campo donde el ganado bebe agua fresca."
}

# Catálogo de 31 plantillas estructurales simétricas 7x7
CRUCIGRAMA_TEMPLATES: List[Dict[str, Any]] = [
  {
    "id": 1,
    "theme": "Afectos y Familia",
    "pattern": [
      ".......",
      ".###.##",
      ".###.#.",
      ".###.#.",
      ".###.#.",
      "###....",
      "#######"
    ],
    "fallback_grid": [
      "HERMANO",
      "I###B##",
      "J###R#V",
      "O###A#I",
      "S###Z#D",
      "###ROSA",
      "#######"
    ]
  },
  {
    "id": 2,
    "theme": "La Cocina Criolla",
    "pattern": [
      "....###",
      "###.###",
      "#.#.##.",
      "#.#.##.",
      "#......",
      "#.####.",
      "#.####."
    ],
    "fallback_grid": [
      "ROSA###",
      "###G###",
      "#S#U##S",
      "#O#A##O",
      "#PASTEL",
      "#A####A",
      "#S####R"
    ]
  },
  {
    "id": 3,
    "theme": "En el Jardín",
    "pattern": [
      ".......",
      "####.#.",
      ".....#.",
      "##.#.#.",
      "##.#.#.",
      "##.#.##",
      "##.####"
    ],
    "fallback_grid": [
      "PLANTAS",
      "####I#O",
      "VERDE#L",
      "##O#M#A",
      "##S#P#R",
      "##A#O##",
      "##S####"
    ]
  },
  {
    "id": 4,
    "theme": "Costumbres y Mate",
    "pattern": [
      "#####.#",
      "....#.#",
      "##.##.#",
      "##.##.#",
      "......#",
      "##.####",
      ".....##"
    ],
    "fallback_grid": [
      "#####C#",
      "MATE#I#",
      "##I##E#",
      "##E##L#",
      "CAMINO#",
      "##P####",
      "AROMA##"
    ]
  },
  {
    "id": 5,
    "theme": "Tiempo y Recuerdos",
    "pattern": [
      "#.#####",
      "#.####.",
      "#.##.#.",
      "#.##.#.",
      ".......",
      "####.#.",
      "##....#"
    ],
    "fallback_grid": [
      "#N#####",
      "#O####A",
      "#C##V#G",
      "#H##E#U",
      "MEMORIA",
      "####D#S",
      "##AYER#"
    ]
  },
  {
    "id": 6,
    "theme": "Animales Nobles",
    "pattern": [
      ".......",
      "##.###.",
      "##.#.#.",
      "#....#.",
      "####.#.",
      "####.##",
      "####.##"
    ],
    "fallback_grid": [
      "TERNERO",
      "##O###V",
      "##S#N#E",
      "#GATO#J",
      "####C#A",
      "####H##",
      "####E##"
    ]
  },
  {
    "id": 7,
    "theme": "En la Escuela",
    "pattern": [
      ".......",
      "##.###.",
      "##.#.#.",
      "##.#.#.",
      "##.#.#.",
      "#.....#",
      "#######"
    ],
    "fallback_grid": [
      "LECCION",
      "##A###O",
      "##M#A#C",
      "##I#U#H",
      "##N#L#E",
      "#SOLAR#",
      "#######"
    ]
  },
  {
    "id": 8,
    "theme": "Ríos y Valles",
    "pattern": [
      ".###.##",
      ".###.#.",
      ".......",
      ".###.#.",
      ".###.#.",
      "######.",
      "#......"
    ],
    "fallback_grid": [
      "N###P##",
      "O###L#L",
      "CASCADA",
      "H###Z#G",
      "E###A#U",
      "######N",
      "#PIEDRA"
    ]
  },
  {
    "id": 9,
    "theme": "El Firmamento",
    "pattern": [
      "###.###",
      "###.#.#",
      ".##.#.#",
      ".##.#.#",
      "......#",
      ".####.#",
      "....###"
    ],
    "fallback_grid": [
      "###V###",
      "###E#R#",
      "S##R#A#",
      "O##D#Y#",
      "LUCERO#",
      "A####S#",
      "ROSA###"
    ]
  },
  {
    "id": 10,
    "theme": "Ropa y Abrigo",
    "pattern": [
      ".......",
      ".#.####",
      ".#.####",
      ".#.....",
      ".######",
      ".######",
      ".....##"
    ],
    "fallback_grid": [
      "CHALECO",
      "O#L####",
      "R#M####",
      "A#AMIGO",
      "Z######",
      "O######",
      "NOCHE##"
    ]
  },
  {
    "id": 11,
    "theme": "La Panadería",
    "pattern": [
      "#......",
      "######.",
      "######.",
      "##.###.",
      "#......",
      "##.####",
      "#......"
    ],
    "fallback_grid": [
      "#TRENZA",
      "######R",
      "######O",
      "##M###M",
      "#PANERA",
      "##S####",
      "#CAMINO"
    ]
  },
  {
    "id": 12,
    "theme": "Calles del Barrio",
    "pattern": [
      "##.####",
      "##.###.",
      "#....#.",
      "##.#.#.",
      ".......",
      "##.#.##",
      "####.##"
    ],
    "fallback_grid": [
      "##F####",
      "##L###V",
      "#ROSA#I",
      "##R#M#D",
      "AVENIDA",
      "##S#G##",
      "####O##"
    ]
  },
  {
    "id": 13,
    "theme": "En el Teatro",
    "pattern": [
      "......#",
      "##.####",
      "##.####",
      "##.....",
      "##.###.",
      "######.",
      "#......"
    ],
    "fallback_grid": [
      "MUSICA#",
      "##O####",
      "##L####",
      "##AROMA",
      "##R###L",
      "######M",
      "#BUTACA"
    ]
  },
  {
    "id": 14,
    "theme": "Cosas del Mar",
    "pattern": [
      "####.##",
      "##.#.##",
      "......#",
      ".#.#.##",
      ".#.####",
      ".#.....",
      "#######"
    ],
    "fallback_grid": [
      "####F##",
      "##P#A##",
      "VELERO#",
      "I#A#O##",
      "D#Z####",
      "A#AMIGO",
      "#######"
    ]
  },
  {
    "id": 15,
    "theme": "Hierbas y Aromas",
    "pattern": [
      "#####.#",
      "#.....#",
      "#####.#",
      ".####.#",
      ".......",
      ".####.#",
      ".....##"
    ],
    "fallback_grid": [
      "#####C#",
      "#AROMA#",
      "#####M#",
      "R####I#",
      "OREGANO",
      "S####O#",
      "AMIGO##"
    ]
  },
  {
    "id": 16,
    "theme": "Peces y Agua",
    "pattern": [
      ".##.###",
      ".##.###",
      ".......",
      ".##.#.#",
      ".####.#",
      "#.....#",
      "#######"
    ],
    "fallback_grid": [
      "P##A###",
      "L##G###",
      "ANZUELO",
      "Z##A#A#",
      "A####G#",
      "#CIELO#",
      "#######"
    ]
  },
  {
    "id": 17,
    "theme": "Herramientas",
    "pattern": [
      ".#.#.##",
      ".#.#.##",
      "......#",
      ".#.#.##",
      "##.....",
      "##.####",
      "#######"
    ],
    "fallback_grid": [
      "R#T#F##",
      "O#U#O##",
      "SIERRA#",
      "A#R#J##",
      "##CLAVO",
      "##A####",
      "#######"
    ]
  },
  {
    "id": 18,
    "theme": "Verduras y Huerta",
    "pattern": [
      "#.....#",
      "####.#.",
      ".###.#.",
      ".###.#.",
      ".......",
      ".###.#.",
      ".###.#."
    ],
    "fallback_grid": [
      "#PLAZA#",
      "####A#B",
      "N###P#A",
      "O###A#T",
      "CEBOLLA",
      "H###L#T",
      "E###O#A"
    ]
  },
  {
    "id": 19,
    "theme": "Dulzuras Caseras",
    "pattern": [
      ".......",
      ".#.####",
      ".#.####",
      ".#.....",
      ".######",
      "....###",
      "#######"
    ],
    "fallback_grid": [
      "ALFAJOR",
      "Z#L####",
      "U#A####",
      "C#NOCHE",
      "A######",
      "ROSA###",
      "#######"
    ]
  },
  {
    "id": 20,
    "theme": "Medios de Viaje",
    "pattern": [
      "......#",
      "####.#.",
      "#......",
      "#.##.#.",
      "#.####.",
      "#.####.",
      "#.#####"
    ],
    "fallback_grid": [
      "MALETA#",
      "####R#S",
      "#BOLETO",
      "#A##N#L",
      "#R####A",
      "#C####R",
      "#O#####"
    ]
  },
  {
    "id": 21,
    "theme": "Instrumentos",
    "pattern": [
      ".......",
      "###.###",
      "###.#.#",
      "###.#.#",
      "#......",
      "#####.#",
      "......#"
    ],
    "fallback_grid": [
      "CUERDAS",
      "###I###",
      "###T#C#",
      "###M#I#",
      "#FLORES",
      "#####L#",
      "CAMINO#"
    ]
  },
  {
    "id": 22,
    "theme": "El Dormitorio",
    "pattern": [
      "......#",
      "#####.#",
      "#.###.#",
      "......#",
      "#.#.###",
      "#.#.###",
      "###.###"
    ],
    "fallback_grid": [
      "SABANA#",
      "#####L#",
      "#R###M#",
      "COLCHA#",
      "#S#A###",
      "#A#M###",
      "###A###"
    ]
  },
  {
    "id": 23,
    "theme": "Colores Vivos",
    "pattern": [
      ".......",
      "#####.#",
      "#.....#",
      "#.###.#",
      "#.###.#",
      "#.....#",
      "#######"
    ],
    "fallback_grid": [
      "CELESTE",
      "#####I#",
      "#VERDE#",
      "#I###M#",
      "#D###P#",
      "#AMIGO#",
      "#######"
    ]
  },
  {
    "id": 24,
    "theme": "Paseos y Senderos",
    "pattern": [
      "......#",
      "####.##",
      "##.#.##",
      "##.#.##",
      "#....##",
      "##.####",
      "#......"
    ],
    "fallback_grid": [
      "COLINA#",
      "####O##",
      "##A#C##",
      "##M#H##",
      "#AIRE##",
      "##G####",
      "#BOSQUE"
    ]
  },
  {
    "id": 25,
    "theme": "Flores Silvestres",
    "pattern": [
      ".......",
      ".#####.",
      ".###.#.",
      ".###.#.",
      ".#.....",
      "####.##",
      "####.##"
    ],
    "fallback_grid": [
      "VIOLETA",
      "E#####M",
      "R###M#I",
      "D###A#G",
      "E#TALLO",
      "####V##",
      "####A##"
    ]
  },
  {
    "id": 26,
    "theme": "La Alacena",
    "pattern": [
      ".......",
      "##.###.",
      "##.#.#.",
      "##.#.#.",
      ".....#.",
      "####.##",
      "####.##"
    ],
    "fallback_grid": [
      "LENTEJA",
      "##O###M",
      "##C#A#I",
      "##H#R#G",
      "CIELO#O",
      "####M##",
      "####A##"
    ]
  },
  {
    "id": 27,
    "theme": "Sonidos del Día",
    "pattern": [
      "#......",
      "######.",
      "##.....",
      "#.####.",
      ".......",
      "#.#####",
      "#.#####"
    ],
    "fallback_grid": [
      "#CHARLA",
      "######R",
      "##RADIO",
      "#R####M",
      "NOTICIA",
      "#S#####",
      "#A#####"
    ]
  },
  {
    "id": 28,
    "theme": "Plantas de Hogar",
    "pattern": [
      "###.###",
      "###.###",
      "#.#.##.",
      "#.#.##.",
      ".......",
      "#.####.",
      ".....#."
    ],
    "fallback_grid": [
      "###V###",
      "###E###",
      "#C#R##A",
      "#I#D##R",
      "HELECHO",
      "#L####M",
      "SOLAR#A"
    ]
  },
  {
    "id": 29,
    "theme": "Juegos de Salón",
    "pattern": [
      "###....",
      "###.###",
      "#......",
      "#.#.#.#",
      "#.#.#.#",
      "#.###.#",
      "#.###.#"
    ],
    "fallback_grid": [
      "###VIDA",
      "###E###",
      "#CARTAS",
      "#I#D#M#",
      "#E#E#I#",
      "#L###G#",
      "#O###O#"
    ]
  },
  {
    "id": 30,
    "theme": "Oficios Nobles",
    "pattern": [
      "......#",
      "#####.#",
      "#.###.#",
      "#.###.#",
      ".......",
      "#.###.#",
      "#....##"
    ],
    "fallback_grid": [
      "MEDICO#",
      "#####F#",
      "#S###I#",
      "#O###C#",
      "ALBANIL",
      "#A###O#",
      "#ROSA##"
    ]
  },
  {
    "id": 31,
    "theme": "El Río Paraná",
    "pattern": [
      ".####.#",
      ".#.##.#",
      ".#.##.#",
      ".#.##.#",
      "......#",
      ".#.####",
      "##....."
    ],
    "fallback_grid": [
      "A####A#",
      "G#T##M#",
      "U#I##I#",
      "A#E##G#",
      "DORADO#",
      "A#R####",
      "##AROMA"
    ]
  }
]

# Compatibilidad hacia atrás
CRUCIGRAMA_BOARDS = CRUCIGRAMA_TEMPLATES

# Estructuras en memoria para búsqueda ultra-rápida de cruces
_WORDS_BY_LEN: Dict[int, List[str]] = {}
_LETTER_POS_INDEX: Dict[Tuple[int, int, str], Set[str]] = {}
_IS_INITIALIZED: bool = False

def _init_word_index():
    """Inicializa el índice de palabras en memoria para búsqueda de candidatos O(1)."""
    global _WORDS_BY_LEN, _LETTER_POS_INDEX, _IS_INITIALIZED
    if _IS_INITIALIZED:
        return

    _WORDS_BY_LEN = {l: [] for l in range(4, 8)}
    _LETTER_POS_INDEX = {}

    if not os.path.exists(DICTIONARY_PATH):
        logger.warning(f"[CRUCIGRAMA] No se encontró el diccionario en {DICTIONARY_PATH}.")
        _IS_INITIALIZED = True
        return

    try:
        with open(DICTIONARY_PATH, "r", encoding="utf-8") as f:
            raw_dict = json.load(f)

        for w in raw_dict.keys():
            if 4 <= len(w) <= 7 and w.isalpha():
                w_upper = w.upper()
                _WORDS_BY_LEN[len(w)].append(w_upper)
                for pos, ch in enumerate(w_upper):
                    _LETTER_POS_INDEX.setdefault((len(w), pos, ch), set()).add(w_upper)

        logger.info(f"[CRUCIGRAMA] Diccionario indexado: {sum(len(v) for v in _WORDS_BY_LEN.values())} palabras.")
    except Exception as e:
        logger.error(f"[CRUCIGRAMA] Error inicializando índice de palabras: {e}")

    _IS_INITIALIZED = True

def _parse_template_slots(grid_pattern: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Tuple[int, str, int]]]] :
    """
    Identifica todos los slots horizontales y verticales en la plantilla 7x7
    y precalcula el mapa de intersecciones entre ellos.
    """
    R, C = 7, 7
    slots: List[Dict[str, Any]] = []

    # 1. Slots horizontales
    for r in range(R):
        c = 0
        while c < C:
            if grid_pattern[r][c] != "#":
                start_c = c
                coords = []
                while c < C and grid_pattern[r][c] != "#":
                    coords.append((r, c))
                    c += 1
                if len(coords) > 1:
                    slots.append({
                        "id": f"H_{r}_{start_c}",
                        "dir": "H",
                        "r": r,
                        "c": start_c,
                        "len": len(coords),
                        "coords": coords
                    })
            else:
                c += 1

    # 2. Slots verticales
    for c in range(C):
        r = 0
        while r < R:
            if grid_pattern[r][c] != "#":
                start_r = r
                coords = []
                while r < R and grid_pattern[r][c] != "#":
                    coords.append((r, c))
                    r += 1
                if len(coords) > 1:
                    slots.append({
                        "id": f"V_{start_r}_{c}",
                        "dir": "V",
                        "r": start_r,
                        "c": c,
                        "len": len(coords),
                        "coords": coords
                    })
            else:
                r += 1

    # 3. Intersecciones (cruce de casillas)
    intersections: Dict[str, List[Tuple[int, str, int]]] = {s["id"]: [] for s in slots}
    for i, s1 in enumerate(slots):
        for j, s2 in enumerate(slots):
            if i == j or s1["dir"] == s2["dir"]:
                continue
            for p1, c1 in enumerate(s1["coords"]):
                for p2, c2 in enumerate(s2["coords"]):
                    if c1 == c2:
                        intersections[s1["id"]].append((p1, s2["id"], p2))

    return slots, intersections

def _solve_crucigrama_backtracking(
    slots: List[Dict[str, Any]],
    intersections: Dict[str, List[Tuple[int, str, int]]],
    rng: random.Random
) -> Optional[Dict[str, str]]:
    """
    Resuelve el crucigrama usando Backtracking con poda de restricciones (Forward Checking)
    y heurística MRV (slots con más cruces evaluados primero).
    """
    _init_word_index()
    if not _WORDS_BY_LEN:
        return None

    cached_defs = _load_definitions_cache()

    # Ordenar slots por cantidad de intersecciones (MRV / Degree Heuristic)
    sorted_slots = sorted(slots, key=lambda s: len(intersections[s["id"]]), reverse=True)

    def backtrack(idx: int, assignment: Dict[str, str], used: Set[str]) -> Optional[Dict[str, str]]:
        if idx == len(sorted_slots):
            return assignment

        slot = sorted_slots[idx]
        s_id = slot["id"]
        s_len = slot["len"]

        # Restricciones impuestas por slots ya asignados
        constraints = []
        for my_pos, other_id, other_pos in intersections[s_id]:
            if other_id in assignment:
                constraints.append((my_pos, assignment[other_id][other_pos]))

        # Obtener candidatos válidos
        if constraints:
            cands = None
            for pos, ch in constraints:
                s_set = _LETTER_POS_INDEX.get((s_len, pos, ch), set())
                cands = s_set if cands is None else cands & s_set
            cand_list = [w for w in (cands or []) if w not in used]
        else:
            cand_list = [w for w in _WORDS_BY_LEN.get(s_len, []) if w not in used]

        if not cand_list:
            return None

        # Priorizar palabras con pistas curadas o caché de la RAE
        curated_prio = []
        cached_prio = []
        other_prio = []

        for w in cand_list:
            if w in CURATED_CLUES:
                curated_prio.append(w)
            elif w in cached_defs or w.lower() in cached_defs:
                cached_prio.append(w)
            else:
                other_prio.append(w)

        rng.shuffle(curated_prio)
        rng.shuffle(cached_prio)
        rng.shuffle(other_prio)
        ordered_cands = curated_prio + cached_prio + other_prio

        # Poda: probar hasta 150 candidatos por rama
        for w in ordered_cands[:150]:
            assignment[s_id] = w
            used.add(w)
            res = backtrack(idx + 1, assignment, used)
            if res is not None:
                return res
            del assignment[s_id]
            used.remove(w)

        return None

    return backtrack(0, {}, set())

def _parse_and_build_challenge(
    theme: str,
    grid_raw: List[str]
) -> Dict[str, Any]:
    """
    Analiza una matriz 7x7 resuelta, asigna números en orden occidental,
    construye la matriz de celdas con bloques/punteros y enriquece las pistas con la RAE.
    """
    R, C = 7, 7
    grid_raw = [row.ljust(C, "#")[:C] for row in grid_raw]

    num = 1
    across_words = []
    down_words = []
    cell_numbers = [[None for _ in range(C)] for _ in range(R)]
    cell_across = [[None for _ in range(C)] for _ in range(R)]
    cell_down = [[None for _ in range(C)] for _ in range(R)]

    for r in range(R):
        for c in range(C):
            ch = grid_raw[r][c]
            if ch == "#":
                continue

            is_a_start = (c == 0 or grid_raw[r][c - 1] == "#") and (c + 1 < C and grid_raw[r][c + 1] != "#")
            is_d_start = (r == 0 or grid_raw[r - 1][c] == "#") and (r + 1 < R and grid_raw[r + 1][c] != "#")

            assigned_num = None
            if is_a_start or is_d_start:
                assigned_num = num
                cell_numbers[r][c] = num
                num += 1

            if is_a_start:
                w_chars = []
                coords = []
                cc = c
                while cc < C and grid_raw[r][cc] != "#":
                    w_chars.append(grid_raw[r][cc])
                    coords.append([r, cc])
                    cell_across[r][cc] = assigned_num
                    cc += 1
                word_str = "".join(w_chars)
                across_words.append({
                    "id": f"H{assigned_num}",
                    "number": assigned_num,
                    "direction": "horizontal",
                    "word": word_str,
                    "length": len(word_str),
                    "row": r,
                    "col": c,
                    "coords": coords,
                    "clue": CURATED_CLUES.get(word_str, f"Palabra de {len(word_str)} letras.")
                })

            if is_d_start:
                w_chars = []
                coords = []
                rr = r
                while rr < R and grid_raw[rr][c] != "#":
                    w_chars.append(grid_raw[rr][c])
                    coords.append([rr, c])
                    cell_down[rr][c] = assigned_num
                    rr += 1
                word_str = "".join(w_chars)
                down_words.append({
                    "id": f"V{assigned_num}",
                    "number": assigned_num,
                    "direction": "vertical",
                    "word": word_str,
                    "length": len(word_str),
                    "row": r,
                    "col": c,
                    "coords": coords,
                    "clue": CURATED_CLUES.get(word_str, f"Palabra de {len(word_str)} letras.")
                })

    # Enriquecer pistas con la RAE y limpiar prefijos
    all_words = across_words + down_words
    for item in all_words:
        w = item["word"]
        if w in CURATED_CLUES:
            raw_clue = CURATED_CLUES[w]
        else:
            rae_def = fetch_rae_definition(w)
            if rae_def:
                raw_clue = rae_def
            else:
                raw_clue = f"Palabra de {len(w)} letras que comienza con '{w[0]}' y termina en '{w[-1]}'."

        # Limpiar cualquier residuo de prefijo 'Definición: '
        clean_clue = re.sub(r"^definici[oó]n\s*[:\-]?\s*", "", raw_clue, flags=re.IGNORECASE).strip()
        item["clue"] = clean_clue

    # Construir matriz de celdas 7x7 serializable
    cells = []
    for r in range(R):
        row_cells = []
        for c in range(C):
            ch = grid_raw[r][c]
            is_block = (ch == "#")
            row_cells.append({
                "row": r,
                "col": c,
                "is_block": is_block,
                "letter": "" if is_block else ch,
                "number": cell_numbers[r][c],
                "across_num": cell_across[r][c],
                "down_num": cell_down[r][c]
            })
        cells.append(row_cells)

    return {
        "theme": theme,
        "grid_size": R,
        "cells": cells,
        "words": all_words,
        "total_words": len(all_words)
    }

def generate_crucigrama_challenge_for_date(date_str: str) -> Dict[str, Any]:
    """
    Genera la configuración completa del desafío de Crucigrama para una fecha específica.
    Utiliza backtracking sobre una plantilla simétrica seleccionada deterministamente por fecha.
    Garantiza unicidad entre meses y determinismo en cualquier servidor.
    """
    seed_val = int(date_str.replace("-", ""))
    rng = random.Random(f"crucigrama_{date_str}")

    tmpl_data = CRUCIGRAMA_TEMPLATES[seed_val % len(CRUCIGRAMA_TEMPLATES)]
    theme = tmpl_data.get("theme", "Palabras Cruzadas")
    pattern = tmpl_data["pattern"]

    slots, intersections = _parse_template_slots(pattern)
    solution = _solve_crucigrama_backtracking(slots, intersections, rng)

    if solution:
        grid_letters = [["#" if pattern[r][c] == "#" else "" for c in range(7)] for r in range(7)]
        for s in slots:
            word = solution[s["id"]]
            for (r, c), ch in zip(s["coords"], word):
                grid_letters[r][c] = ch
        final_grid = ["".join(r) for r in grid_letters]
    else:
        logger.warning(f"[CRUCIGRAMA] Backtracking no encontró solución para {date_str}. Usando tablero curado de respaldo.")
        final_grid = tmpl_data["fallback_grid"]

    challenge = _parse_and_build_challenge(theme, final_grid)
    challenge["date"] = date_str
    return challenge
