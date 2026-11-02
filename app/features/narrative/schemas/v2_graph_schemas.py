from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.features.narrative.schemas.rules_schemas import CondicionSchema
from app.features.narrative.schemas.catalog_schemas import ImpactoAfinidadSchema
from app.features.narrative.enums import TipoCondicionEnum, DireccionEventoEspecialEnum

# ============================================================================
# MODELOS PYDANTIC: MOTOR NARRATIVO V2 BASADO EN GRAFOS DE DECISIÓN
# ============================================================================

class ImpactoRecursoSchema(BaseModel):
    recurso: str = Field(..., description="Clave del recurso modificado (oro, pueblo, ejercito, fe)")
    delta: int = Field(..., description="Variación entera positiva o negativa")

class DesenlaceNodoSchema(BaseModel):
    nodo: str = Field(..., description="ID del nodo destino posible de la opción")
    peso: float = Field(default=1.0, description="Peso relativo del desenlace para el sorteo ponderado")

class OpcionNodoSchema(BaseModel):
    id: str = Field(..., description="Identificador único de la opción (ej: opt_1, opt_apoyar_marcus)")
    texto: str = Field(..., description="Texto visible en el botón de decisión para el jugador")
    siguiente_nodo: Optional[str] = Field(
        default=None,
        description="ID del nodo destino fijo (almacenado solo en el servidor). Usado si 'desenlaces' está vacío."
    )
    desenlaces: List[DesenlaceNodoSchema] = Field(
        default_factory=list,
        description="Desenlaces ponderados opcionales: la opción sortea uno al azar según sus pesos (ej. 40/60)"
    )
    condiciones: List[CondicionSchema] = Field(
        default_factory=list,
        description="Condiciones de estado (recursos, afinidad, personajes, cartas, tags) requeridas para habilitar esta opción"
    )
    bloqueo_modo: str = Field(
        default="deshabilitada",
        description="'deshabilitada' (se muestra con candado e indicación) o 'oculta' (opción secreta que no se muestra si no cumple)"
    )

class OpcionClienteSchema(BaseModel):
    id: str = Field(..., description="Identificador de la opción seleccionable")
    texto: str = Field(..., description="Texto que el usuario lee en el botón")
    disponible: bool = Field(default=True, description="True si cumple todos los requisitos para ser seleccionada")
    motivo_bloqueo: Optional[str] = Field(default=None, description="Texto explicativo para el jugador si la opción está bloqueada")

class NodoNarrativoSchema(BaseModel):
    id: str = Field(..., description="ID único del nodo dentro del grafo")
    hablante_id: str = Field(..., description="ID del orador ('narrador' para eventos, o ID de personaje como 'pj_elena')")
    texto: str = Field(..., description="Diálogo o narración correspondiente a este paso")
    imagen: Optional[str] = Field(default=None, description="Imagen ilustrativa opcional del nodo (solo si el operador la cargó)")
    es_final: bool = Field(default=False, description="True si es una hoja de desenlace que concluye el grafo")
    opciones: List[OpcionNodoSchema] = Field(default_factory=list, description="Opciones disponibles si no es final")
    resultado_texto: str = Field(default="", description="Texto de consecuencia y cierre si es_final=True")
    impactos_recursos: List[ImpactoRecursoSchema] = Field(default_factory=list, description="Impactos en recursos si es_final=True")
    impactos_afinidad: List[ImpactoAfinidadSchema] = Field(default_factory=list, description="Impactos en afinidad si es_final=True")
    impactos_tags: List[str] = Field(default_factory=list, description="Tags permanentes otorgados al reino si es_final=True")

    @staticmethod
    def _generar_motivo_bloqueo(cond: Any) -> str:
        """Genera un mensaje explicativo amigable para el jugador sobre el requisito faltante."""
        tipo = getattr(cond, "tipo", None)
        if isinstance(tipo, str):
            try:
                tipo = TipoCondicionEnum(tipo)
            except ValueError:
                pass

        if tipo == TipoCondicionEnum.COMPARAR_RECURSO:
            clave = (getattr(cond, "clave", "recurso") or "recurso").capitalize()
            op = getattr(cond, "operador", ">=") or ">="
            op_str = getattr(op, "value", str(op))
            val = getattr(cond, "valor", 0)
            return f"Requiere {clave} {op_str} {val}"
        elif tipo == TipoCondicionEnum.TIENE_PERSONAJE:
            pj = getattr(cond, "personaje_id", "personaje")
            return f"Requiere a {pj} en la corte"
        elif tipo == TipoCondicionEnum.AFINIDAD_PERSONAJE:
            pj = getattr(cond, "personaje_id", "personaje")
            op = getattr(cond, "operador", ">=") or ">="
            op_str = getattr(op, "value", str(op))
            val = getattr(cond, "valor", 0)
            return f"Requiere afinidad {op_str} {val} con {pj}"
        elif tipo == TipoCondicionEnum.TIENE_TAG:
            tag = getattr(cond, "tag", "atributo")
            return f"Requiere atributo '{tag}'"
        elif tipo == TipoCondicionEnum.TIENE_CARTA:
            carta = getattr(cond, "carta_id", "objeto")
            return f"Requiere poseer la carta '{carta}'"

        return "Requisitos no cumplidos"

    def to_cliente_schema(self, run_data: Optional[Dict[str, Any]] = None) -> "NodoClienteSchema":
        """Convierte el nodo interno a la versión sanitizada para el cliente, evaluando condiciones si se provee run_data."""
        from app.features.narrative.engine.rule_engine import evaluar_condicion

        opciones_sanitizadas: List[OpcionClienteSchema] = []
        for opt in self.opciones:
            cumple = True
            motivo: Optional[str] = None

            if run_data and opt.condiciones:
                for cond in opt.condiciones:
                    cond_dict = cond.model_dump() if hasattr(cond, "model_dump") else cond
                    if not evaluar_condicion(cond_dict, run_data):
                        cumple = False
                        motivo = self._generar_motivo_bloqueo(cond)
                        break

            # Si no cumple y es una opción oculta (secreta), no se revela al cliente
            if not cumple and getattr(opt, "bloqueo_modo", "deshabilitada") == "oculta":
                continue

            opciones_sanitizadas.append(
                OpcionClienteSchema(
                    id=opt.id,
                    texto=opt.texto,
                    disponible=cumple,
                    motivo_bloqueo=motivo if not cumple else None
                )
            )

        return NodoClienteSchema(
            id=self.id,
            hablante_id=self.hablante_id,
            texto=self.texto,
            imagen=self.imagen,
            es_final=self.es_final,
            opciones=opciones_sanitizadas,
            resultado_texto=self.resultado_texto if self.es_final else "",
            impactos_recursos=self.impactos_recursos if self.es_final else [],
            impactos_afinidad=self.impactos_afinidad if self.es_final else [],
            impactos_tags=self.impactos_tags if self.es_final else []
        )

class NodoClienteSchema(BaseModel):
    id: str
    hablante_id: str
    texto: str
    imagen: Optional[str] = None
    es_final: bool = False
    opciones: List[OpcionClienteSchema] = Field(default_factory=list)
    resultado_texto: str = ""
    impactos_recursos: List[ImpactoRecursoSchema] = Field(default_factory=list)
    impactos_afinidad: List[ImpactoAfinidadSchema] = Field(default_factory=list)
    impactos_tags: List[str] = Field(default_factory=list)

# ============================================================================
# COLECCIONES EN MONGODB: EVENTOS Y CONVERSACIONES V2
# ============================================================================

class EventoV2GrafoSchema(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único del evento V2 (ej: evt_peste_puerto_v2)")
    universo_id: str = Field(default="corte_medieval", description="Universo al que pertenece")
    titulo: str = Field(..., description="Título visible del evento")
    imagen: str = Field(..., description="Ruta de la imagen de cabecera/fondo")
    peso_base: float = Field(default=100.0, description="Peso base para el sorteo ponderado")
    tags_tematicos: List[str] = Field(default_factory=list, description="Etiquetas temáticas para sinergias con corte o cartas")
    requisitos_eventos_previos: List[str] = Field(
        default_factory=list,
        description="Lista de IDs de eventos que deben haberse jugado previamente para habilitar este evento en el sorteo"
    )
    requisitos_personajes: List[str] = Field(
        default_factory=list,
        description="Lista de IDs de personajes que deben estar en la corte para que este evento pueda ocurrir"
    )
    condiciones_disparo: List[CondicionSchema] = Field(
        default_factory=list,
        description="Condiciones de estado del reino requeridas para habilitar el evento en el sorteo"
    )
    nodo_raiz: str = Field(..., description="ID del nodo inicial del árbol")
    nodos: Dict[str, NodoNarrativoSchema] = Field(..., description="Diccionario de nodos indexados por su ID")

    model_config = {"populate_by_name": True}

class ConversacionV2GrafoSchema(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único de la conversación V2")
    universo_id: str = Field(default="corte_medieval", description="Universo al que pertenece")
    titulo: str = Field(..., description="Título visible de la conversación")
    imagen: str = Field(..., description="Ruta de la imagen de fondo de corte")
    requisitos: List[str] = Field(
        default_factory=list,
        description="Lista de IDs de personajes que deben estar vivos en la corte activa para que ocurra"
    )
    condiciones_disparo: List[CondicionSchema] = Field(
        default_factory=list,
        description="Condiciones de estado del reino requeridas para habilitar la conversación en el sorteo"
    )
    nodo_raiz: str = Field(..., description="ID del nodo inicial del diálogo")
    nodos: Dict[str, NodoNarrativoSchema] = Field(..., description="Diccionario de nodos indexados por su ID")

    model_config = {"populate_by_name": True}

class EventoEspecialV2GrafoSchema(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único del evento especial (ej: esp_lealtad_elena)")
    universo_id: str = Field(default="corte_medieval", description="Universo al que pertenece")
    personaje_id: str = Field(..., description="ID del personaje de corte que dispara este evento por umbral de afinidad")
    direccion: DireccionEventoEspecialEnum = Field(..., description="'lealtad' (afinidad alta) o 'traicion' (afinidad baja)")
    titulo: str = Field(..., description="Título visible del evento especial")
    imagen: str = Field(default="/assets/narrative/eventos/default.webp", description="Ruta de la imagen de cabecera/fondo")
    nodo_raiz: str = Field(..., description="ID del nodo inicial del árbol")
    nodos: Dict[str, NodoNarrativoSchema] = Field(..., description="Diccionario de nodos indexados por su ID")

    model_config = {"populate_by_name": True}

# ============================================================================
# REQUESTS Y RESPONSES DE LA API V2
# ============================================================================

class AvanzarNodoV2Request(BaseModel):
    date: str = Field(..., description="Fecha del desafío en formato YYYY-MM-DD")
    opcion_id: str = Field(..., description="ID de la opción seleccionada por el jugador")

class EstadoGrafoV2Response(BaseModel):
    fase_actual: str = Field(..., description="Fase de la partida tras la transición")
    grafo_id: str = Field(..., description="ID del evento o conversación activo")
    tipo: str = Field(..., description="'evento' o 'conversacion'")
    titulo: str = Field(..., description="Título del evento o conversación")
    imagen: str = Field(..., description="Imagen ilustrativa")
    nodo_actual: NodoClienteSchema = Field(..., description="Nodo activo en el que se encuentra el jugador")
    afinidad: Optional[Dict[str, int]] = Field(default=None, description="Afinidades actualizadas si es nodo final")
    recursos: Optional[Dict[str, int]] = Field(default=None, description="Recursos actualizados si es nodo final")
    finalizacion: Optional[Dict[str, Any]] = Field(default=None, description="Datos del epílogo si la partida terminó (derrota)")
    status: str = Field(default="CONTINUA", description="Estado de la partida ('CONTINUA', 'VICTORIA', 'DERROTA')")
    puntos_ganados: Optional[int] = Field(default=None, description="Puntos acreditados por finalizar la partida (solo en transición terminal)")

# ============================================================================
# VALIDACIÓN ESTÁTICA DE GRAFOS V2
# ============================================================================

class ValidarGrafoV2Request(BaseModel):
    tipo: Optional[str] = Field(
        default=None,
        description="'evento', 'conversacion' o 'evento_especial'. Obligatorio si se envía 'grafo'."
    )
    grafo_id: Optional[str] = Field(default=None, description="ID del grafo almacenado a validar")
    universo_id: Optional[str] = Field(default=None, description="Filtro por universo al validar en lote")
    grafo: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Grafo inline a validar sin persistirlo (útil desde el editor admin)"
    )

class HallazgoValidacionSchema(BaseModel):
    codigo: str = Field(..., description="Código estable del hallazgo")
    mensaje: str = Field(..., description="Descripción legible del problema")
    nodo_id: Optional[str] = Field(default=None, description="Nodo involucrado, si aplica")
    opcion_id: Optional[str] = Field(default=None, description="Opción involucrada, si aplica")

class ResultadoValidacionGrafoSchema(BaseModel):
    tipo: str = Field(..., description="Tipo de grafo validado")
    grafo_id: Optional[str] = Field(default=None, description="ID del grafo validado")
    valido: bool = Field(..., description="True si no hay errores bloqueantes")
    errores: List[HallazgoValidacionSchema] = Field(default_factory=list, description="Problemas bloqueantes")
    advertencias: List[HallazgoValidacionSchema] = Field(default_factory=list, description="Problemas no bloqueantes")

class ValidarGrafoV2Response(BaseModel):
    resultados: List[ResultadoValidacionGrafoSchema] = Field(default_factory=list)
    total: int = Field(default=0, description="Cantidad de grafos validados")
    invalidos: int = Field(default=0, description="Cantidad de grafos con errores")
