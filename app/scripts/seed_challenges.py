import logging
from datetime import datetime, timezone
from app.core.database import get_database
from app.scripts.seed_sopa_letras import seed_sopa_letras_challenges

logger = logging.getLogger(__name__)

WORDLE_AGOSTO_2026 = [
    {"date": "2026-08-01", "solution": "VIAJE", "hints": ["Paseo o traslado a otro lugar para conocer o descansar"]},
    {"date": "2026-08-02", "solution": "FAROL", "hints": ["Aparato con luz para alumbrar las calles de noche"]},
    {"date": "2026-08-03", "solution": "ROSAS", "hints": ["Flores perfumadas de espinas y pétalos delicados"]},
    {"date": "2026-08-04", "solution": "TRIGO", "hints": ["Cereal dorado que se muele para hacer harina y pan"]},
    {"date": "2026-08-05", "solution": "MANOS", "hints": ["Extremidades con dedos que usamos para acariciar y crear"]},
    {"date": "2026-08-06", "solution": "OTOÑO", "hints": ["Estación del año en que las hojas caen doradas"]},
    {"date": "2026-08-07", "solution": "COSTA", "hints": ["Orilla de la tierra que linda con el mar o río"]},
    {"date": "2026-08-08", "solution": "RADIO", "hints": ["Aparato fiel que nos acompaña con música y noticias"]},
    {"date": "2026-08-09", "solution": "TANGO", "hints": ["Música y danza tradicional rioplatense muy sentida"]},
    {"date": "2026-08-10", "solution": "SABOR", "hints": ["Sensación que dejan los alimentos ricos en el paladar"]},
    {"date": "2026-08-11", "solution": "CORAL", "hints": ["Estructura submarina de colores vivos y vistosos"]},
    {"date": "2026-08-12", "solution": "NIEVE", "hints": ["Copos blancos y fríos que caen del cielo en invierno"]},
    {"date": "2026-08-13", "solution": "PATIO", "hints": ["Espacio descubierto en el centro o fondo de la casa"]},
    {"date": "2026-08-14", "solution": "FERIA", "hints": ["Puestos al aire libre donde comprar frutas y artesanías"]},
    {"date": "2026-08-15", "solution": "GATOS", "hints": ["Mascotas ágiles, curiosas y de andar silencioso"]},
    {"date": "2026-08-16", "solution": "CARRO", "hints": ["Vehículo de ruedas tirado por caballos o empujado a mano"]},
    {"date": "2026-08-17", "solution": "NUBES", "hints": ["Formaciones blancas de vapor que flotan en el cielo"]},
    {"date": "2026-08-18", "solution": "TAZON", "hints": ["Recipiente hondo y grande para tomar café con leche o sopa"]},
    {"date": "2026-08-19", "solution": "POEMA", "hints": ["Texto de versos que expresa sentimientos profundos"]},
    {"date": "2026-08-20", "solution": "TELON", "hints": ["Gran cortina de terciopelo que abre la obra en el teatro"]},
    {"date": "2026-08-21", "solution": "MUSEO", "hints": ["Lugar donde se cuidan y exhiben obras de arte e historia"]},
    {"date": "2026-08-22", "solution": "AGUAS", "hints": ["Líquido vital cristalino de ríos, mares y arroyos"]},
    {"date": "2026-08-23", "solution": "PECES", "hints": ["Animales que nadan con aletas bajo el agua"]},
    {"date": "2026-08-24", "solution": "ALDEA", "hints": ["Pueblo pequeño y tranquilo con pocos habitantes"]},
    {"date": "2026-08-25", "solution": "SENDA", "hints": ["Camino estrecho de tierra para andar a pie"]},
    {"date": "2026-08-26", "solution": "DANZA", "hints": ["Movimiento rítmico del cuerpo siguiendo la música"]},
    {"date": "2026-08-27", "solution": "PIANO", "hints": ["Instrumento musical de teclas blancas y negras"]},
    {"date": "2026-08-28", "solution": "BOTON", "hints": ["Pieza redonda para abrochar abrigos y camisas"]},
    {"date": "2026-08-29", "solution": "CALOR", "hints": ["Sensación tibia y agradable que nos da el sol de verano"]},
    {"date": "2026-08-30", "solution": "SALUD", "hints": ["Estado pleno de bienestar del cuerpo y la mente"]},
    {"date": "2026-08-31", "solution": "FAROS", "hints": ["Torres luminosas que guían a los navegantes en la noche"]},
]

WORDLE_SEPTIEMBRE_2026 = [
    {"date": "2026-09-01", "solution": "AMIGO", "hints": ["Compañero leal con quien compartimos momentos lindos"]},
    {"date": "2026-09-02", "solution": "RAYOS", "hints": ["Líneas brillantes de luz que emite el sol al amanecer"]},
    {"date": "2026-09-03", "solution": "MATES", "hints": ["Infusión tradicional caliente que se comparte en ronda"]},
    {"date": "2026-09-04", "solution": "GLOBO", "hints": ["Esfera liviana y colorida que se infla y flota"]},
    {"date": "2026-09-05", "solution": "TRUCO", "hints": ["Juego de naipes tradicional y pícaro muy argentino"]},
    {"date": "2026-09-06", "solution": "CALLE", "hints": ["Camino pavimentado entre veredas y casas de la ciudad"]},
    {"date": "2026-09-07", "solution": "MARES", "hints": ["Grandes extensiones de agua salada con olas y mareas"]},
    {"date": "2026-09-08", "solution": "GOTAS", "hints": ["Pequeñas esferas de agua que caen de la lluvia"]},
    {"date": "2026-09-09", "solution": "ALMAS", "hints": ["Esencia interior y espiritual que da vida a las personas"]},
    {"date": "2026-09-10", "solution": "CLARA", "hints": ["Limpia, transparente y llena de luminosidad"]},
    {"date": "2026-09-11", "solution": "VIDAS", "hints": ["Historias y experiencias que acumulamos con el tiempo"]},
    {"date": "2026-09-12", "solution": "LLAMA", "hints": ["Fuego pequeño o animal andino de lana suave"]},
    {"date": "2026-09-13", "solution": "PASTO", "hints": ["Hierba verde y corta que cubre el suelo de los jardines"]},
    {"date": "2026-09-14", "solution": "AROMA", "hints": ["Olor agradable que desprenden las flores o un buen café"]},
    {"date": "2026-09-15", "solution": "SUELO", "hints": ["Superficie firme sobre la que caminamos y construimos"]},
    {"date": "2026-09-16", "solution": "VAPOR", "hints": ["Gas invisible o niebla que sale del agua muy caliente"]},
    {"date": "2026-09-17", "solution": "TELAS", "hints": ["Tejidos suaves para confeccionar manteles y vestidos"]},
    {"date": "2026-09-18", "solution": "PLATA", "hints": ["Metal precioso y brillante de color blanco grisáceo"]},
    {"date": "2026-09-19", "solution": "FOCOS", "hints": ["Bombillas que dan iluminación en las habitaciones"]},
    {"date": "2026-09-20", "solution": "ARPAS", "hints": ["Instrumentos musicales de cuerdas que se tocan con los dedos"]},
    {"date": "2026-09-21", "solution": "TORRE", "hints": ["Construcción alta y esbelta que domina el paisaje"]},
    {"date": "2026-09-22", "solution": "PALCO", "hints": ["Asiento privilegiado en el teatro para ver la función"]},
    {"date": "2026-09-23", "solution": "HORAS", "hints": ["Fracciones de sesenta minutos que marcan el transcurrir del día"]},
    {"date": "2026-09-24", "solution": "CORTE", "hints": ["Conjunto de personas que acompañaban a los antiguos reyes"]},
    {"date": "2026-09-25", "solution": "MUNDO", "hints": ["El planeta entero que habitamos con todas sus culturas"]},
    {"date": "2026-09-26", "solution": "BARRA", "hints": ["Mostrador largo de madera donde se sirven cafés y tragos"]},
    {"date": "2026-09-27", "solution": "PECHO", "hints": ["Parte del cuerpo donde late el corazón con fuerza"]},
    {"date": "2026-09-28", "solution": "RITMO", "hints": ["Compás cadencioso de la música que invita a bailar"]},
    {"date": "2026-09-29", "solution": "NOCHE", "hints": ["Tiempo oscuro y sereno entre el atardecer y el amanecer"]},
    {"date": "2026-09-30", "solution": "COPAS", "hints": ["Vasos de cristal con pie fino para brindar en las fiestas"]},
]

WORDLE_OCTUBRE_2026 = [
    {"date": "2026-10-01", "solution": "PLAYA", "hints": ["Lugar con arena y mar para descansar y tomar sol"]},
    {"date": "2026-10-02", "solution": "ARBOL", "hints": ["Tiene tronco, ramas y da sombra con sus hojas"]},
    {"date": "2026-10-03", "solution": "CIELO", "hints": ["Espacio infinito azul donde vuelan los pájaros"]},
    {"date": "2026-10-04", "solution": "CANTO", "hints": ["Melodía que se produce con la voz humana"]},
    {"date": "2026-10-05", "solution": "LIBRO", "hints": ["Páginas con historias interesantes para leer"]},
    {"date": "2026-10-06", "solution": "CAMPO", "hints": ["Terreno verde y abierto fuera de la ciudad"]},
    {"date": "2026-10-07", "solution": "FLORA", "hints": ["Conjunto de flores y plantas de una región"]},
    {"date": "2026-10-08", "solution": "BRISA", "hints": ["Viento suave y fresco en una tarde agradable"]},
    {"date": "2026-10-09", "solution": "HOGAR", "hints": ["Lugar donde vive y se reúne la familia con cariño"]},
    {"date": "2026-10-10", "solution": "NOBLE", "hints": ["Persona generosa y de sentimientos limpios"]},
    {"date": "2026-10-11", "solution": "DULCE", "hints": ["Sabor agradable como la miel o el azúcar"]},
    {"date": "2026-10-12", "solution": "BARCO", "hints": ["Medio de transporte que navega sobre el agua"]},
    {"date": "2026-10-13", "solution": "VERDE", "hints": ["El color de la hierba fresca y la esperanza"]},
    {"date": "2026-10-14", "solution": "RELOJ", "hints": ["Aparato que marca las horas y los minutos"]},
    {"date": "2026-10-15", "solution": "PLAZA", "hints": ["Espacio público con bancos, árboles y paseos"]},
    {"date": "2026-10-16", "solution": "SOLAR", "hints": ["Relacionado con la energía y la luz del sol"]},
    {"date": "2026-10-17", "solution": "MONTE", "hints": ["Gran elevación natural del terreno"]},
    {"date": "2026-10-18", "solution": "RUMBO", "hints": ["Dirección o sentido que tomamos al caminar"]},
    {"date": "2026-10-19", "solution": "PERLA", "hints": ["Esfera brillante y valiosa nacida en el mar"]},
    {"date": "2026-10-20", "solution": "SELVA", "hints": ["Bosque tropical tupido y lleno de vida"]},
    {"date": "2026-10-21", "solution": "CALMA", "hints": ["Paz, serenidad y ausencia de apuros"]},
    {"date": "2026-10-22", "solution": "FUEGO", "hints": ["Produce luz y calor con sus brasas y llamas"]},
    {"date": "2026-10-23", "solution": "ARENA", "hints": ["Partículas finas y doradas en la orilla del mar"]},
    {"date": "2026-10-24", "solution": "LUCES", "hints": ["Destellos que iluminan y quitan la oscuridad"]},
    {"date": "2026-10-25", "solution": "RISAS", "hints": ["Sonido alegre que demuestra felicidad"]},
    {"date": "2026-10-26", "solution": "SUEÑO", "hints": ["Descanso profundo y reparador durante la noche"]},
    {"date": "2026-10-27", "solution": "FRUTA", "hints": ["Alimento fresco, sano y dulce de los árboles"]},
    {"date": "2026-10-28", "solution": "VALLE", "hints": ["Terreno llano rodeado por montañas"]},
    {"date": "2026-10-29", "solution": "LLAVE", "hints": ["Herramienta que abre puertas y cofres"]},
    {"date": "2026-10-30", "solution": "PLUMA", "hints": ["Parte ligera que recubre a las aves"]},
    {"date": "2026-10-31", "solution": "CANAL", "hints": ["Cauce artificial por donde corre el agua"]},
]

async def seed_wordle_challenges():
    """Siembra los desafíos diarios de Wordle para Agosto, Septiembre y Octubre 2026 de forma idempotente."""
    db = get_database()
    now_utc = datetime.now(timezone.utc)
    inserted_or_updated = 0

    all_challenges = WORDLE_AGOSTO_2026 + WORDLE_SEPTIEMBRE_2026 + WORDLE_OCTUBRE_2026

    for item in all_challenges:
        doc = {
            "game_id": "wordle",
            "date": item["date"],
            "difficulty": "standard",
            "title": f"Palabra del Día ({item['date']})",
            "config": {
                "solution": item["solution"],
                "word_length": 5,
                "max_attempts": 6,
                "hints": item["hints"]
            },
            "updated_at": now_utc
        }

        await db["daily_challenges"].update_one(
            {
                "game_id": "wordle",
                "date": item["date"],
                "difficulty": "standard"
            },
            {
                "$set": doc,
                "$setOnInsert": {"created_at": now_utc}
            },
            upsert=True
        )
        inserted_or_updated += 1

    logger.info(f"[DESAFÍOS] {inserted_or_updated} desafíos de Wordle sincronizados (Agosto, Septiembre y Octubre 2026).")
