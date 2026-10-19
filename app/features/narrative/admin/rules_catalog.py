"""
rules_catalog.py
Catálogo canónico de disparadores, operadores y tipos de acciones del motor ECA
utilizado para poblar los selectores y desplegables de la Torre de Control (Frontend Admin).
"""

from typing import Dict, Any
from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    CategoriaCartaEnum,
    TipoResultadoEnum
)

def obtener_catalogo_reglas_dict() -> Dict[str, Any]:
    """Retorna el catálogo canónico de disparadores, operadores y acciones para el panel de administración."""
    return {
        "disparadores": [
            {"clave": DisparadorEnum.AL_OBTENER.value, "label": "Al obtener la carta o reclutar personaje"},
            {"clave": DisparadorEnum.CADA_MES.value, "label": "Al comenzar cada mes"},
            {"clave": DisparadorEnum.EN_EVENTO_POSITIVO.value, "label": "Tras un desenlace positivo en el evento"},
            {"clave": DisparadorEnum.EN_EVENTO_NEGATIVO.value, "label": "Tras un desenlace negativo en el evento"},
            {"clave": DisparadorEnum.AL_FINAL_PARTIDA.value, "label": "Al completar los 12 meses"}
        ],
        "operadores": [
            {"clave": OperadorEnum.MAYOR_IGUAL.value, "label": "Mayor o igual (>=)"},
            {"clave": OperadorEnum.MENOR_IGUAL.value, "label": "Menor o igual (<=)"},
            {"clave": OperadorEnum.MAYOR.value, "label": "Mayor estricto (>)"},
            {"clave": OperadorEnum.MENOR.value, "label": "Menor estricto (<)"},
            {"clave": OperadorEnum.IGUAL.value, "label": "Igual (==)"},
            {"clave": OperadorEnum.DISTINTO.value, "label": "Distinto (!=)"}
        ],
        "tipos_condicion": [
            {"clave": TipoCondicionEnum.COMPARAR_RECURSO.value, "label": "Comparar valor de un recurso"},
            {"clave": TipoCondicionEnum.TIENE_PERSONAJE.value, "label": "Tiene a un personaje específico en la corte"},
            {"clave": TipoCondicionEnum.AFINIDAD_PERSONAJE.value, "label": "Nivel de afinidad con un personaje"},
            {"clave": TipoCondicionEnum.TIENE_TAG.value, "label": "Posee un tag pasivo activo"},
            {"clave": TipoCondicionEnum.TIENE_CARTA.value, "label": "Posee una carta en el inventario"}
        ],
        "tipos_accion": [
            {"clave": TipoAccionEnum.MODIFICAR_RECURSO.value, "label": "Modificar cantidad de un recurso"},
            {"clave": TipoAccionEnum.MODIFICAR_AFINIDAD.value, "label": "Modificar afinidad con personaje"},
            {"clave": TipoAccionEnum.OTORGAR_TAG.value, "label": "Otorgar un tag pasivo permanente"},
            {"clave": TipoAccionEnum.AMORTIGUAR_DANIO.value, "label": "Amortiguar pérdida de un recurso"}
        ],
        "tipos_calculo": [
            {"clave": TipoCalculoEnum.FIJO.value, "label": "Cantidad Fija (+10, -5)"},
            {"clave": TipoCalculoEnum.PORCENTUAL.value, "label": "Porcentual (+15%, -20%)"}
        ],
        "categorias_carta": [
            {"clave": CategoriaCartaEnum.ITEM.value, "label": "Ítem"},
            {"clave": CategoriaCartaEnum.BONUS.value, "label": "Bonus"},
            {"clave": CategoriaCartaEnum.PERSONAJE.value, "label": "Personaje / Recluta"}
        ],
        "tipos_resultado": [
            {"clave": TipoResultadoEnum.POSITIVO.value, "label": "Positivo (Verde / Victoria)"},
            {"clave": TipoResultadoEnum.NEGATIVO.value, "label": "Negativo (Rojo / Pérdida)"},
            {"clave": TipoResultadoEnum.NEUTRO.value, "label": "Neutro (Gris / Balance)"}
        ]
    }
