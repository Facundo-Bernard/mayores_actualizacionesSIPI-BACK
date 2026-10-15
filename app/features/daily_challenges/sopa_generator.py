"""
sopa_generator.py
Módulo para la generación de desafíos diarios de Sopa de Letras accesibles para adultos mayores.
Coloca 4 palabras temáticas en una cuadrícula 8x8 (solo horizontal y vertical) y
obtiene definiciones de la RAE con máscara de spoilers para el botón de pistas.
"""

import random
import logging
from typing import Dict, Any, List, Tuple
from app.core.rae_client import fetch_rae_definition

logger = logging.getLogger(__name__)

# Banco temático curado y cercano a la cultura para personas mayores
SOPA_THEMES_CATALOG: List[Tuple[str, List[str], List[str]]] = [
    ('Frutas Frescas', ['MANZANA', 'PERA', 'LIMON', 'UVA'], ['Roja y crujiente', 'Verde y jugosa', 'Amarillo y acido', 'Viene en racimos']),
    ('El Desayuno', ['CAFE', 'TOSTADA', 'LECHE', 'MATE'], ['Bebida caliente matinal', 'Pan crujiente y dorado', 'Bebida blanca nutritiva', 'Infusion tradicional']),
    ('En el Jardin', ['ROSAS', 'CLAVEL', 'JAZMIN', 'PINO'], ['Flor de espinas y aroma', 'Flor con volados', 'Flor blanca de rico perfume', 'Arbol siempre verde']),
    ('Animales de Campo', ['CABALLO', 'VACA', 'OVEJA', 'PATO'], ['Noble corcel', 'Nos da rica leche', 'Da lana abrigada', 'Nada en la laguna']),
    ('Instrumentos', ['GUITARRA', 'PIANO', 'FLAUTA', 'ARPA'], ['Tiene seis cuerdas', 'Teclas blancas y negras', 'Instrumento de viento', 'Cuerdas de sonido angelical']),
    ('La Cocina', ['OLLA', 'SARTEN', 'CUCHARA', 'PLATO'], ['Para hacer guisos', 'Para freir y dorar', 'Para tomar sopa', 'Donde se sirve la comida']),
    ('Cosas del Mar', ['BARCO', 'ARENA', 'PLAYA', 'CORAL'], ['Navega sobre el agua', 'Dorada en la orilla', 'Lugar para tomar sol', 'Formacion submarina']),
    ('La Huerta', ['TOMATE', 'LECHUGA', 'ZAPALLO', 'HABA'], ['Rojo y de ensalada', 'Hojas verdes frescas', 'Grande de pulpa naranja', 'Legumbre tierna']),
    ('Medios de Viaje', ['TREN', 'AVION', 'AUTO', 'COCHE'], ['Corre sobre vias', 'Vuela por el cielo', 'Vehiculo de cuatro ruedas', 'Medio de transporte']),
    ('Ropa de Abrigo', ['BUFANDA', 'SACO', 'GUANTE', 'GORRO'], ['Protege el cuello', 'Prenda con botones', 'Abriga las manos', 'Para la cabeza']),
    ('La Costura', ['AGUJA', 'HILO', 'BOTON', 'DEDAL'], ['Tiene un fino ojo', 'Hebra para coser', 'Para abrochar camisas', 'Protege el dedo']),
    ('Oficios Nobles', ['PINTOR', 'HERRERO', 'PASTOR', 'CHOFER'], ['Llena de color la pared', 'Trabaja el metal', 'Cuida a las ovejas', 'Conduce el colectivo']),
    ('Aves Cantoras', ['CANARIO', 'GORRION', 'PALOMA', 'LORO'], ['Amarillo y cantor', 'Pajarito de ciudad', 'Ave de la paz', 'Ave que repite palabras']),
    ('Dulzuras Criollas', ['PASTEL', 'ALFAJOR', 'MIEL', 'DULCE'], ['Rico bocado de fiesta', 'Dos tapitas con dulce', 'Manjar de las abejas', 'Sabor azucarado']),
    ('En la Plaza', ['BANCO', 'ARBOL', 'FUENTE', 'CAMINO'], ['Para sentarse a charlar', 'Da linda sombra', 'Mana agua cristalina', 'Sendero para pasear']),
    ('En la Escuela', ['LAPIZ', 'CUADERNO', 'PIZARRA', 'REGLA'], ['Para escribir y dibujar', 'Hojas para anotar', 'Donde escribe la maestra', 'Mide lineas rectas']),
    ('Rios y Valles', ['ARROYO', 'CASCADA', 'VALLE', 'MONTE'], ['Corriente de agua chica', 'Caida de agua sonora', 'Terreno bajo y fertil', 'Elevacion natural']),
    ('El Mate Criollo', ['YERBA', 'BOMBILLA', 'TERMO', 'PAVA'], ['Hojas verdes molidas', 'Cana o metal para sorber', 'Mantiene el agua caliente', 'Hierve agua en la cocina']),
    ('Arboles Buenos', ['ROBLE', 'SAUCE', 'CEIBO', 'PINO'], ['Madera muy firme', 'Ramas que caen al agua', 'Nuestra flor nacional', 'Aroma fresco de bosque']),
    ('Picada Criolla', ['PAN', 'QUESO', 'JAMON', 'SALAME'], ['Horneado y crujiente', 'Lacteo sabroso', 'Fiambreria tradicional', 'Embutido curado']),
    ('En el Teatro', ['TELON', 'ACTOR', 'PALCO', 'BUTACA'], ['Cortina que sube y baja', 'Interpreta su papel', 'Ubicacion privilegiada', 'Asiento comodo']),
    ('El Tiempo', ['RELOJ', 'MINUTO', 'HORA', 'TIEMPO'], ['Marca los momentos', 'Sesenta segundos', 'Sesenta minutos', 'Pasa sin detenerse']),
    ('El Firmamento', ['ESTRELLA', 'SOL', 'LUNA', 'COMETA'], ['Brilla en la noche', 'Rey del dia', 'Companera nocturna', 'Cuerpo celeste con cola']),
    ('El Dormitorio', ['ALMOHADA', 'SABANA', 'CAMA', 'COBIJA'], ['Apoyo de la cabeza', 'Tela suave y fresca', 'Mueble de descanso', 'Abrigo de lana']),
    ('Colores Vivos', ['AZUL', 'ROJO', 'VERDE', 'DORADO'], ['Como el mar', 'Como la manzana', 'Color de esperanza', 'Color del oro']),
    ('Calles del Barrio', ['CALLE', 'VEREDA', 'PLAZA', 'ESQUINA'], ['Camino del barrio', 'Por donde caminamos', 'Lugar de juegos', 'Cruce de dos calles']),
    ('Paseos Verdes', ['PARQUE', 'LAGUNA', 'BOSQUE', 'SENDERO'], ['Extenso espacio verde', 'Espejo de agua tranquilo', 'Arboleda tupida', 'Caminito de tierra']),
    ('Flores Silvestres', ['LIRIO', 'VIOLETA', 'MALVA', 'CALA'], ['Elegante flor blanca', 'Flor silvestre morada', 'Flor de tonos suaves', 'Elegante y erguida']),
    ('Los Recuerdos', ['FOTO', 'CARTA', 'DIARIO', 'MEDALLA'], ['Guarda una sonrisa', 'Escrita de puno y letra', 'Noticias de ayer', 'Premio al merito']),
    ('Cosas de la Casa', ['MESA', 'SILLA', 'PUERTA', 'VENTANA'], ['Donde come la familia', 'Para sentarse comodo', 'Entrada a la casa', 'Da luz y aire']),
    ('La Panaderia', ['FLAUTA', 'BOLLO', 'FACTURA', 'CREMA'], ['Pan alargado y crocante', 'Pancito redondo', 'Dulzura de hojaldre', 'Relleno suave']),
    ('Vientos y Clima', ['BRISA', 'VIENTO', 'NIEBLA', 'LLUVIA'], ['Soplo suave de aire', 'Mueve los arboles', 'Humo blanco de humedad', 'Agua bendita que cae']),
    ('Hierbas Frescas', ['MENTA', 'ROMERO', 'TOMILLO', 'LAUREL'], ['Fresca y perfumada', 'Aroma para carnes', 'Hierba silvestre sabrosa', 'Hoja para el tuco']),
    ('Peces de Rio', ['DORADO', 'SURUBI', 'TRUCHA', 'BAGRE'], ['Pez rey de escamas de oro', 'Gigante de bigotes', 'Pez de aguas cristalinas', 'Pez de fondo de rio']),
    ('Herramientas', ['MARTILLO', 'PINZA', 'CLAVO', 'SIERRA'], ['Para golpear y fijar', 'Sujeta con fuerza', 'Punta de metal', 'Para cortar madera']),
    ('Verduras Sanas', ['ACELGA', 'PAPA', 'BATATA', 'CEBOLLA'], ['Hojas verdes grandes', 'Tuberculo noble para pure', 'Dulce y asada al horno', 'Hace llorar al picar']),
    ('Bebidas Sabrosas', ['JUGO', 'MALTA', 'AGUA', 'SIDRA'], ['Exprimido de frutas', 'Bebida de cereal tostado', 'Liquido vital transparente', 'Brindis de fin de ano']),
    ('En los Libros', ['LIBRO', 'NOVELA', 'CUENTO', 'POEMA'], ['Paginas de sabiduria', 'Historia larga y atrapante', 'Relato breve de ficcion', 'Versos rimados']),
    ('Mascotas Fieles', ['PERRO', 'GATO', 'LORO', 'CONEJO'], ['El mejor amigo del hombre', 'Felino de siestas al sol', 'Ave de plumas verdes', 'De orejas largas']),
    ('Cumpleanos', ['TORTA', 'REGALO', 'VELAS', 'FIESTA'], ['Dulce con crema para soplar', 'Paquete con mono sorpresa', 'Se apagan pidiendo deseos', 'Reunion con musica']),
    ('Ropa de Verano', ['REMERA', 'MALLA', 'CAMISA', 'SOMBRERO'], ['Prenda de algodon ligera', 'Para nadar en la pileta', 'Prenda con cuello y botones', 'Cubre del sol']),
    ('La Alacena', ['ARROZ', 'FIDEOS', 'HARINA', 'AZUCAR'], ['Granos blancos para guiso', 'Pastas de domingo', 'Base de todo buen pan', 'Endulza la vida']),
    ('Sonidos del Dia', ['RADIO', 'RELOJ', 'TIMBRE', 'PASOS'], ['Voces que acompanan', 'Tic tac sereno', 'Avisa que llego visita', 'Andar de las personas']),
    ('Plantas Verdes', ['HELECHO', 'POTUS', 'MALVON', 'CACTUS'], ['Hojas colgantes frondosas', 'Planta noble de agua', 'Flor colorida de patio', 'Guarda agua en espinas']),
    ('Por la Ciudad', ['TAXI', 'TRANVIA', 'TREN', 'SUBTE'], ['Coche amarillo y negro', 'Viajaba sobre rieles viejos', 'Conecta pueblos y ciudades', 'Bajo tierra sin demoras']),
    ('Juegos de Mesa', ['DOMINO', 'LOTERIA', 'AJEDREZ', 'CARTAS'], ['Fichas con puntos negros', 'Se cantan los numeros', 'Reyes, torres y peones', 'Baraja espanola']),
    ('Calzado Comodo', ['ZAPATO', 'BOTA', 'MOCASIN', 'BOTIN'], ['De cuero para pasear', 'Para lluvia o campo', 'Calzado suave sin cordones', 'Para jugar al futbol']),
    ('Deportes Nobles', ['FUTBOL', 'BOCHAS', 'TENIS', 'REMO'], ['Pasion de multitudes', 'Arrime y bochazo en la tierra', 'Raqueta y pelota amarilla', 'Navegar con palas']),
    ('Citricos Dulces', ['NARANJA', 'POMELO', 'LIMA', 'MANDARIN'], ['Jugo dulce matinal', 'Rosado y amarguito', 'Pequeno y aromatico', 'Gajos faciles de pelar']),
    ('Musica Clasica', ['VIOLIN', 'CHELO', 'TAMBOR', 'CORNETA'], ['Instrumento de arco dulce', 'Cuerda grave y profunda', 'Marca el ritmo del compas', 'Sonido brillante de bronce']),
    ('Cosas del Bano', ['TOALLA', 'JABON', 'ESPEJO', 'PEINE'], ['Para secarse suave', 'Espuma perfumada', 'Refleja nuestra imagen', 'Acomoda el cabello']),
    ('Primavera Serena', ['PIMPOLLO', 'BROTE', 'POLEN', 'NIDO'], ['Flor antes de abrir', 'Primera hojita verde', 'Polvillo de las flores', 'Hogar de los pajaritos']),
    ('Cosas de Papel', ['SOBRE', 'POSTAL', 'HOJA', 'FOLLETO'], ['Guarda una carta sellada', 'Foto y saludo de viaje', 'Papel blanco para escribir', 'Papel impreso informativo']),
    ('En el Balcon', ['MACETA', 'BARANDA', 'FAROL', 'PLANTA'], ['Tierra para las flores', 'Proteccion de hierro', 'Luz para la noche fresca', 'Verde en altura']),
    ('Fauna Silvestre', ['CIERVO', 'ZORRO', 'LIEBRE', 'ERIZO'], ['Elegante de astas', 'Astuto y colorado', 'Corre veloz por el campo', 'Pequeno y con puas']),
    ('Postres Caseros', ['COMPOTA', 'FLAN', 'BUDIN', 'ARROZ'], ['Fruta cocida con canela', 'Con dulce de leche y crema', 'Masa horneada esponjosa', 'Con leche y azucar']),
    ('Metales Nobles', ['CUARZO', 'ORO', 'PLATA', 'BRONCE'], ['Cristal de roca brillante', 'Metal amarillo valioso', 'Metal blanco reluciente', 'Aleacion para campanas']),
    ('Tormenta de Verano', ['RAYO', 'TRUENO', 'VIENTO', 'CIELO'], ['Luz repentina en el cielo', 'Sonido retumbante lejano', 'Corriente veloz de aire', 'Espacio inmenso azul']),
    ('En la Ferreteria', ['TORNILLO', 'TUERCA', 'MECHA', 'PINZA'], ['Gira y ajusta con rosca', 'Asegura el perno', 'Para perforar agujeros', 'Herramienta de agarre']),
    ('Gente Querida', ['PANADERO', 'CARTERO', 'MODISTA', 'VECINO'], ['Hornea el pan de cada dia', 'Trae noticias y cartas', 'Cose y ajusta vestidos', 'El que vive al lado']),
    ('Cosas del Campo', ['ESTANCIA', 'RANCHO', 'MOLINO', 'SURCO'], ['Gran casa rural', 'Vivienda tradicional campera', 'Gira sus aspas con viento', 'Linea arada en la tierra']),
    ('Frutos de Otono', ['NUEZ', 'ALMENDRA', 'CASTANA', 'MANI'], ['Cascara dura y rica', 'Fruto seco tostado', 'Asada en invierno', 'Tostado para picar']),
    ('En el Desvan', ['COFRE', 'LAMPARA', 'CAJON', 'MALETA'], ['Caja de tesoros y llave', 'Alumbra los rincones', 'Compartimento corredizo', 'Para guardar ropa de viaje']),
    ('Partes del Arbol', ['RAIZ', 'TRONCO', 'RAMA', 'HOJA'], ['Bajo tierra da soporte', 'Cuerpo de madera firme', 'Se extiende hacia el sol', 'Verde que cae en otono']),
    ('Merienda Sabrosa', ['CORTADO', 'VAINILLA', 'CANELA', 'MASITA'], ['Cafe con un toque de leche', 'Aroma dulce y suave', 'Polvo aromatico para cafe', 'Galletita crocante']),
    ('Aves de Rio', ['GARZA', 'CISNE', 'CHAJA', 'PATO'], ['Patas largas y elegante', 'Blanco de cuello curvado', 'Grito protector de la pampa', 'Pico ancho nadador']),
    ('Peces de Mar', ['MERLUZA', 'ATUN', 'CORVINA', 'SALMON'], ['Pescado clasico con pure', 'Pez rapido de aguas hondas', 'Pez de costa atlantica', 'Carne rosada deliciosa']),
    ('Flores con Aroma', ['FRESIAS', 'AZAHAR', 'LAVANDA', 'NARCISO'], ['Ramilletes de colores', 'Flor de los naranjos', 'Violeta que perfuma roperos', 'Flor de primavera']),
    ('Tejidos de Abrigo', ['LANA', 'TELAR', 'CHAL', 'PONCHO'], ['Fibra natural de oveja', 'Madera donde se teje', 'Manta para los hombros', 'Prenda tradicional criolla']),
    ('Especias del Hogar', ['OREGANO', 'PIMENTON', 'COMINO', 'LAUREL'], ['Hierba para la pizza', 'Polvo rojo sabroso', 'Toque criollo para empanadas', 'Hoja que va a la cacerola']),
    ('En el Cuadro', ['PINCEL', 'LIENZO', 'OLEO', 'MARCO'], ['Cerdas para pintar', 'Tela tensada blanca', 'Pintura espesa y noble', 'Madera que rodea la obra']),
    ('Insectos Nobles', ['GRILLO', 'VAQUITA', 'ABEJA', 'HORMIGA'], ['Canta en las noches tibias', 'Rojita de San Antonio', 'Fabrica miel dorada', 'Trabajadora incansable']),
    ('Comidas Criollas', ['ASADO', 'EMPANADA', 'LOCRO', 'GUISO'], ['Carne a la parrilla de domingo', 'Masa rellena al horno', 'Olla patria de maiz', 'Comida caliente de cuchara']),
    ('Noche Serena', ['LUCERO', 'SERENO', 'CALMA', 'SILENCIO'], ['Estrella brillante matinal', 'Frescor nocturno suave', 'Paz interior sin prisa', 'Ausencia de ruido']),
    ('Vajilla Querida', ['VASO', 'TAZA', 'JARRA', 'COPA'], ['Para tomar agua fresca', 'Para el cafe con leche', 'Sirve limonada fria', 'Para brindar en familia']),
    ('En la Estacion', ['ANDEN', 'BOLETO', 'SILBATO', 'VIA'], ['Plataforma donde se espera', 'Pasaje para viajar', 'Avisa la salida del tren', 'Rieles de hierro largos']),
    ('Colores Pasteles', ['CELESTE', 'ROSA', 'LILA', 'CREMA'], ['Color del cielo patrio', 'Suave como los petalos', 'Tono violeta claro', 'Tono calido y manteca']),
    ('El Costurero', ['CINTA', 'DEDAL', 'CIERRE', 'RETAZO'], ['Mide telas con centimetros', 'Protector para no pincharse', 'Dientes para unir camperas', 'Pedazo sobrante de tela']),
    ('Juegos de Infancia', ['TROMPO', 'RAYUELA', 'BOLITA', 'ARO'], ['Gira con una cuerda', 'Se salta en una pata', 'Esferas de vidrio de colores', 'Se hace rodar en la vereda']),
    ('En el Almacen', ['BALANZA', 'BOLSA', 'PESO', 'CAJA'], ['Pesa frutas y verduras', 'Para llevar las compras', 'Medida de los kilos', 'Donde se guarda el cambio']),
    ('Caminos Criollos', ['HUELLA', 'ALAMBRE', 'SENDERO', 'PASO'], ['Marca de rueda en la tierra', 'Cerca que delimita el campo', 'Caminito entre los pastos', 'Cruce de arroyo']),
    ('Cosas de Madera', ['BANCO', 'TABLA', 'REPISA', 'BAUL'], ['Asiento firme de madera', 'Para picar la carne', 'Estante para adornos', 'Gran arca para guardar']),
    ('Dulzuras de Masa', ['CREMONA', 'CHIPA', 'TORTITA', 'ROSCA'], ['Hojaldre salado con grasa', 'Bocaditos tibios con queso', 'Panecillo mendocino', 'Dulce tradicional de pascua']),
    ('Prendas Elegantes', ['TRAJE', 'CORBATA', 'CAMISA', 'SACO'], ['Ropa fina para festejo', 'Nudo al cuello elegante', 'Prenda limpia planchada', 'Abrigo de corte sastre']),
    ('En el Puerto', ['MUELLE', 'ANCLA', 'FARO', 'RED'], ['Pasarela sobre el mar', 'Fija el barco en su lugar', 'Luz giratoria de noche', 'Para recoger la pesca']),
    ('Aves de Vuelo', ['GAVIOTA', 'HORNERO', 'HALCON', 'COLIBRI'], ['Vuela sobre las olas', 'Constructor de casita de barro', 'Rapaz de mirada aguda', 'Pajarito que besa las flores']),
    ('Paseo por el Centro', ['GALERIA', 'CINE', 'KIOSCO', 'FAROLA'], ['Paseo techado de locales', 'Pantalla grande y pochoclo', 'Golosinas y revistas', 'Ilumina la avenida']),
    ('Sabores Regionales', ['CONSERVA', 'SALAME', 'DULCE', 'QUESO'], ['Frascos caseros sellados', 'Embutido de colonia caroya', 'Mermelada de membrillo', 'De campo estacionado']),
    ('Instrumentos Viento', ['TROMPETA', 'SAXOFON', 'GAITA', 'CORNO'], ['Sonido triunfal y agudo', 'Sonido calido y jazzero', 'Soplo con bolsa de cuero', 'Instrumento curvo de bronce']),
    ('Encuentros Lindos', ['ABRAZO', 'SONRISA', 'REUNION', 'FESTEJO'], ['Gesto de carino apretado', 'Alegria en el rostro', 'Juntada con la familia', 'Momento de alegria compartida']),
    ('Tiempo de Descanso', ['SIESTA', 'REPOSO', 'PAZ', 'SUENO'], ['Dormir un ratito a la tarde', 'Tranquilidad para el cuerpo', 'Serenidad en el alma', 'Descanso reparador']),
    ('Historias de Siempre', ['LEYENDA', 'MITO', 'FABULA', 'CUENTO'], ['Relato popular antiguo', 'Historia de dioses y heroes', 'Cuento con moraleja', 'Narracion para nietos']),
]

def generate_word_search(words: List[str], grid_size: int = 8, seed: int = None) -> Tuple[List[List[str]], List[Dict[str, Any]]]:
    """
    Coloca 4 palabras de forma horizontal (izq a der) o vertical (arriba a abajo)
    en una cuadrícula de 8x8 sin diagonales ni palabras invertidas.
    Rellena los espacios vacíos con letras de relleno en español.
    """
    if seed is not None:
        random.seed(seed)
    sorted_words = sorted(words, key=len, reverse=True)
    max_attempts = 300
    for _ in range(max_attempts):
        grid = [['' for _ in range(grid_size)] for _ in range(grid_size)]
        placed_words = []
        success = True
        for word in sorted_words:
            w_len = len(word)
            positions = []
            for r in range(grid_size):
                for c in range(grid_size):
                    if c + w_len <= grid_size:
                        positions.append((r, c, 'H'))
                    if r + w_len <= grid_size:
                        positions.append((r, c, 'V'))
            random.shuffle(positions)
            placed = False
            for r, c, direction in positions:
                can_place = True
                for i, char in enumerate(word):
                    curr_r = r if direction == 'H' else r + i
                    curr_c = c + i if direction == 'H' else c
                    if grid[curr_r][curr_c] != '' and grid[curr_r][curr_c] != char:
                        can_place = False
                        break
                if can_place:
                    for i, char in enumerate(word):
                        curr_r = r if direction == 'H' else r + i
                        curr_c = c + i if direction == 'H' else c
                        grid[curr_r][curr_c] = char
                    end_r = r if direction == 'H' else r + w_len - 1
                    end_c = c + w_len - 1 if direction == 'H' else c
                    placed_words.append({
                        'word': word,
                        'start': [r, c],
                        'end': [end_r, end_c],
                        'direction': direction
                    })
                    placed = True
                    break
            if not placed:
                success = False
                break
        if success:
            fillers = 'ABCDEFLMNORSTUVZ'
            for r in range(grid_size):
                for c in range(grid_size):
                    if grid[r][c] == '':
                        grid[r][c] = random.choice(fillers)
            return grid, placed_words
    raise ValueError(f'No se pudieron ubicar las palabras: {words}')

def generate_sopa_hints(words: List[str], fallback_hints: List[str]) -> List[str]:
    """
    Obtiene definiciones oficiales de la RAE para cada una de las palabras.
    Si no encuentra o falla la conexión, utiliza la pista pedagógica por defecto.
    """
    final_hints = []
    for idx, w in enumerate(words):
        fallback = fallback_hints[idx] if idx < len(fallback_hints) else f"Palabra de {len(w)} letras."
        rae_def = fetch_rae_definition(w)
        if rae_def:
            final_hints.append(f"Definición: {rae_def}")
        else:
            final_hints.append(fallback)
    return final_hints

def generate_sopa_challenge_for_date(date_str: str) -> Dict[str, Any]:
    """
    Genera la configuración completa del desafío de Sopa de Letras para una fecha específica.
    """
    seed_val = int(date_str.replace('-', ''))
    
    # Elegir tema determinísticamente según la fecha para consistencia absoluta
    theme_idx = seed_val % len(SOPA_THEMES_CATALOG)
    theme_name, words, default_hints = SOPA_THEMES_CATALOG[theme_idx]

    # Generar pistas enriquecidas con la RAE
    hints = generate_sopa_hints(words, default_hints)

    # Generar cuadrícula 8x8 accesible
    grid, placed_words = generate_word_search(words, grid_size=8, seed=seed_val)

    return {
        "theme": theme_name,
        "words": words,
        "hints": hints,
        "grid_size": 8,
        "grid": grid,
        "placed_words": placed_words
    }
