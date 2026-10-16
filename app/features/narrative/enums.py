from enum import Enum

class DisparadorEnum(str, Enum):
    AL_OBTENER = "al_obtener"
    CADA_MES = "cada_mes"
    EN_EVENTO_POSITIVO = "en_evento_positivo"
    EN_EVENTO_NEGATIVO = "en_evento_negativo"
    AL_FINAL_PARTIDA = "al_final_partida"

class OperadorEnum(str, Enum):
    MAYOR_IGUAL = ">="
    MENOR_IGUAL = "<="
    MAYOR = ">"
    MENOR = "<"
    IGUAL = "=="
    DISTINTO = "!="

class TipoCondicionEnum(str, Enum):
    COMPARAR_RECURSO = "comparar_recurso"
    TIENE_PERSONAJE = "tiene_personaje"
    AFINIDAD_PERSONAJE = "afinidad_personaje"
    TIENE_TAG = "tiene_tag"
    TIENE_CARTA = "tiene_carta"

class TipoAccionEnum(str, Enum):
    MODIFICAR_RECURSO = "modificar_recurso"
    MODIFICAR_AFINIDAD = "modificar_afinidad"
    OTORGAR_TAG = "otorgar_tag"
    AMORTIGUAR_DANIO = "amortiguar_danio"

class TipoCalculoEnum(str, Enum):
    FIJO = "fijo"
    PORCENTUAL = "porcentual"

class RunPhaseEnum(str, Enum):
    SETUP_CORTE = "SETUP_CORTE"
    SETUP_CARTAS = "SETUP_CARTAS"
    DRAFT_MENSUAL = "DRAFT_MENSUAL"
    TOMA_DECISION_EVENTO = "TOMA_DECISION_EVENTO"
    RESOLVER_CONVERSACION = "RESOLVER_CONVERSACION"
    BALANCE_MES = "BALANCE_MES"
    FINALIZADA = "FINALIZADA"

class TipoResultadoEnum(str, Enum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    NEUTRO = "neutro"

class CategoriaCartaEnum(str, Enum):
    ITEM = "item"
    BONUS = "bonus"
    PERSONAJE = "personaje"

class TipoFinalizacionEnum(str, Enum):
    DERROTA_RECURSO = "derrota_recurso"
    VICTORIA_TIEMPO = "victoria_tiempo"
    DERROTA_GENERAL = "derrota_general"

