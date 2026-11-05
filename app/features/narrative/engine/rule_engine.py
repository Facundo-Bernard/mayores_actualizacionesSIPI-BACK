import logging
from typing import List, Dict, Any, Optional, Union

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum,
    OperacionMatematicaEnum,
)
from app.features.narrative.schemas.rules_schemas import (
    CondicionSchema,
    AccionSchema,
    EfectoSchema,
    AccionReferenciadaSchema,
    PrimitivaOperacionEnum,
)

logger = logging.getLogger(__name__)


def evaluar_condicion(condicion: Any, run_data: Dict[str, Any]) -> bool:
    """
    Evalúa una condición individual contra el estado vivo de la partida.
    Acepta tanto una instancia de CondicionSchema como un dict de MongoDB.
    """
    if isinstance(condicion, dict):
        condicion = CondicionSchema(**condicion)

    tipo = condicion.tipo

    # 1. Comparación de Recurso Numérico (ej: "oro" >= 50)
    if tipo == TipoCondicionEnum.COMPARAR_RECURSO:
        clave = condicion.clave
        if not clave:
            return False
        recursos = run_data.get("recursos", {})
        valor_actual = float(recursos.get(clave, 0))
        valor_objetivo = float(condicion.valor or 0)
        return _comparar_valores(valor_actual, condicion.operador, valor_objetivo)

    # 2. Posesión de Personaje en la Corte Activa
    elif tipo == TipoCondicionEnum.TIENE_PERSONAJE:
        corte = list(run_data.get("afinidad", {}).keys()) or run_data.get("corte_activa", [])
        return condicion.personaje_id in corte

    # 3. Nivel de Afinidad con Personaje
    elif tipo == TipoCondicionEnum.AFINIDAD_PERSONAJE:
        personaje_id = condicion.personaje_id
        if not personaje_id:
            return False
        afinidades = run_data.get("afinidad", {})
        afinidad_actual = float(afinidades.get(personaje_id, 50))
        valor_objetivo = float(condicion.valor or 0)
        return _comparar_valores(afinidad_actual, condicion.operador, valor_objetivo)

    # 4. Posesión de un Tag Activo (de cartas o perks)
    elif tipo == TipoCondicionEnum.TIENE_TAG:
        tags = run_data.get("tags_activos", [])
        return condicion.tag in tags

    # 5. Posesión de Carta en Mano / Inventario
    elif tipo == TipoCondicionEnum.TIENE_CARTA:
        cartas = run_data.get("cartas_en_mano", [])
        return condicion.carta_id in cartas

    return False


def evaluar_condiciones(condiciones: List[Any], run_data: Dict[str, Any]) -> bool:
    """
    Evalúa una lista de condiciones bajo operador lógico AND.
    Si la lista está vacía, se considera True.
    """
    if not condiciones:
        return True
    return all(evaluar_condicion(c, run_data) for c in condiciones)


def _comparar_valores(actual: float, operador: Optional[OperadorEnum], objetivo: float) -> bool:
    """
    Compara dos valores flotantes utilizando el operador relacional provisto.
    """
    if operador == OperadorEnum.MAYOR_IGUAL:
        return actual >= objetivo
    elif operador == OperadorEnum.MENOR_IGUAL:
        return actual <= objetivo
    elif operador == OperadorEnum.MAYOR:
        return actual > objetivo
    elif operador == OperadorEnum.MENOR:
        return actual < objetivo
    elif operador == OperadorEnum.IGUAL:
        return actual == objetivo
    elif operador == OperadorEnum.DISTINTO:
        return actual != objetivo
    return False



def _aplicar_operacion_matematica(
    actual: float,
    operacion: Optional[Union[OperacionMatematicaEnum, str]],
    valor: float,
) -> float:
    """
    Aplica una operación matemática configurada sobre un valor numérico:
    - sumar: actual + valor
    - restar: actual - valor
    - multiplicar: actual * valor
    - dividir: actual / valor (con salvaguarda por división entre 0)
    - porcentual: actual + (actual * (valor / 100))
    - fijar: valor
    """
    op = operacion.value if hasattr(operacion, "value") else str(operacion or "sumar").lower()
    if op == "sumar":
        return actual + valor
    elif op == "restar":
        return actual - valor
    elif op == "multiplicar":
        return actual * valor
    elif op == "dividir":
        if valor == 0:
            logger.warning("División por cero detectada en mutar_estado; se mantiene el valor actual.")
            return actual
        return actual / valor
    elif op == "porcentual":
        return actual + (actual * (valor / 100.0))
    elif op == "fijar":
        return valor
    return actual + valor

def _extraer_primitiva_y_params(
    accion: Any,
    catalogo_acciones: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    Extrae la primitiva ejecutable y los parámetros normalizados tanto de
    AccionSchema (legacy) como de AccionReferenciadaSchema (nuevo desacoplado).
    """
    if isinstance(accion, AccionReferenciadaSchema):
        accion_id = accion.accion_id
        params = accion.parametros.model_dump()
    elif isinstance(accion, dict) and "accion_id" in accion:
        accion_id = accion["accion_id"]
        params = accion.get("parametros", {})
    elif isinstance(accion, AccionSchema):
        accion_id = accion.tipo.value
        params = {
            "clave": accion.clave,
            "valor": accion.valor,
            "tipo_calculo": accion.tipo_calculo.value if accion.tipo_calculo else "fijo",
            "personaje_id": accion.personaje_id,
            "tag": accion.tag,
            "destino": "portador" if not accion.personaje_id else "personaje",
        }
    elif isinstance(accion, dict) and "tipo" in accion:
        accion_id = accion["tipo"]
        params = {
            "clave": accion.get("clave"),
            "valor": accion.get("valor", 0),
            "tipo_calculo": accion.get("tipo_calculo", "fijo"),
            "personaje_id": accion.get("personaje_id"),
            "tag": accion.get("tag"),
            "destino": "portador" if not accion.get("personaje_id") else "personaje",
        }
    else:
        return "", {}

    # Resolver la primitiva a través del catálogo si existe la referencia
    primitiva = accion_id
    if catalogo_acciones and accion_id in catalogo_acciones:
        cat_item = catalogo_acciones[accion_id]
        primitiva = cat_item.get("primitiva") or cat_item.get("tipo_accion") or accion_id

    return str(primitiva), params


def ejecutar_accion(
    accion: Any,
    run_data: Dict[str, Any],
    recursos_definicion: Optional[Dict[str, Dict[str, Any]]] = None,
    duenio_id: Optional[str] = None,
    catalogo_acciones: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Modifica el estado en memoria de run_data según el tipo de acción.
    Soporta formato legacy AccionSchema y nuevo AccionReferenciadaSchema desacoplado.
    """
    primitiva, params = _extraer_primitiva_y_params(accion, catalogo_acciones)
    if not primitiva:
        return

    # 1. Modificar Recurso
    if primitiva in (TipoAccionEnum.MODIFICAR_RECURSO.value, PrimitivaOperacionEnum.MODIFICAR_RECURSO.value):
        clave = params.get("clave")
        if not clave:
            return
        recursos = run_data.setdefault("recursos", {})
        valor_actual = float(recursos.get(clave, 0))
        tipo_calc = params.get("tipo_calculo")
        valor_num = float(params.get("valor") or 0)

        if tipo_calc in (TipoCalculoEnum.PORCENTUAL.value, "porcentual"):
            delta = valor_actual * (valor_num / 100.0)
        else:
            delta = valor_num

        # Si el delta es negativo (daño/pérdida), verificar amortiguadores pasivos
        if delta < 0:
            for mod in run_data.get("modificadores_pasivos", []):
                if mod.get("tipo") == "amortiguar_danio" and (not mod.get("clave") or mod.get("clave") == clave):
                    reduccion = float(mod.get("reduccion_porcentual", 0))
                    if 0 < reduccion <= 100:
                        delta *= (1.0 - (reduccion / 100.0))

        nuevo_valor = round(valor_actual + delta)

        # Clamping de límites dinámicos de partida o definición del universo
        limite_min = None
        limite_max = None
        if run_data.get("limites") and clave in run_data["limites"]:
            limite_min = run_data["limites"][clave].get("min")
            limite_max = run_data["limites"][clave].get("max")
        elif recursos_definicion and clave in recursos_definicion:
            limite_min = recursos_definicion[clave].get("min")
            limite_max = recursos_definicion[clave].get("max")

        if limite_min is not None:
            nuevo_valor = max(float(limite_min), nuevo_valor)
        if limite_max is not None:
            nuevo_valor = min(float(limite_max), nuevo_valor)

        recursos[clave] = int(nuevo_valor)

    # 2. Modificar Afinidad con Personaje
    elif primitiva in (TipoAccionEnum.MODIFICAR_AFINIDAD.value, PrimitivaOperacionEnum.MODIFICAR_AFINIDAD.value):
        destino = params.get("destino", "personaje")
        personaje_target = duenio_id if (destino == "portador" and duenio_id) else params.get("personaje_id")
        if not personaje_target:
            return
        afinidades = run_data.setdefault("afinidad", {})
        actual = int(afinidades.get(personaje_target, 50))
        delta = int(float(params.get("valor") or 0))
        afinidades[personaje_target] = max(0, min(100, actual + delta))

    # 3. Otorgar Tag Pasivo
    elif primitiva in (TipoAccionEnum.OTORGAR_TAG.value, PrimitivaOperacionEnum.OTORGAR_TAG.value):
        tag = params.get("tag")
        if tag:
            tags = run_data.setdefault("tags_activos", [])
            if tag not in tags:
                tags.append(tag)

    # 4. Remover Tag Pasivo
    elif primitiva == PrimitivaOperacionEnum.REMOVER_TAG.value:
        tag = params.get("tag")
        if tag:
            tags = run_data.setdefault("tags_activos", [])
            if tag in tags:
                tags.remove(tag)

    # 5. Amortiguar Daño Pasivo
    elif primitiva in (TipoAccionEnum.AMORTIGUAR_DANIO.value, PrimitivaOperacionEnum.AMORTIGUAR_DANIO.value):
        clave = params.get("clave")
        reduccion = float(params.get("valor") or params.get("porcentaje") or 0)
        mods = run_data.setdefault("modificadores_pasivos", [])
        mods.append({
            "tipo": "amortiguar_danio",
            "clave": clave,
            "reduccion_porcentual": reduccion,
            "fuente": duenio_id,
        })

    # 6. Mutar Estado Genérico y Dinámico
    elif primitiva == PrimitivaOperacionEnum.MUTAR_ESTADO.value:
        ruta = params.get("ruta") or params.get("clave")
        if not ruta:
            return

        op_mat = params.get("operacion_matematica", OperacionMatematicaEnum.SUMAR.value)
        valor_num = float(params.get("valor") or 0.0)

        # A) Recursos: ruta 'recursos.<clave>' o clave directa de recurso
        if ruta.startswith("recursos.") or (recursos_definicion and ruta in recursos_definicion):
            clave_rec = ruta.split(".", 1)[1] if ruta.startswith("recursos.") else ruta
            recursos = run_data.setdefault("recursos", {})
            actual = float(recursos.get(clave_rec, 0))
            nuevo_num = _aplicar_operacion_matematica(actual, op_mat, valor_num)
            delta = nuevo_num - actual

            # Amortiguación si es pérdida
            if delta < 0:
                for mod in run_data.get("modificadores_pasivos", []):
                    if mod.get("tipo") == "amortiguar_danio" and (not mod.get("clave") or mod.get("clave") == clave_rec):
                        reduccion = float(mod.get("reduccion_porcentual", 0))
                        if 0 < reduccion <= 100:
                            delta *= (1.0 - (reduccion / 100.0))
                nuevo_num = actual + delta

            limite_min = None
            limite_max = None
            if run_data.get("limites") and clave_rec in run_data["limites"]:
                limite_min = run_data["limites"][clave_rec].get("min")
                limite_max = run_data["limites"][clave_rec].get("max")
            elif recursos_definicion and clave_rec in recursos_definicion:
                limite_min = recursos_definicion[clave_rec].get("min")
                limite_max = recursos_definicion[clave_rec].get("max")

            if limite_min is not None:
                nuevo_num = max(float(limite_min), nuevo_num)
            if limite_max is not None:
                nuevo_num = min(float(limite_max), nuevo_num)

            recursos[clave_rec] = int(round(nuevo_num))

        # B) Límites dinámicos: 'limites.<clave>.min' o 'limites.<clave>.max'
        elif ruta.startswith("limites."):
            partes = ruta.split(".")
            if len(partes) >= 3:
                clave_rec = partes[1]
                sub_lim = partes[2]  # 'min' | 'max'
                lim_dict = run_data.setdefault("limites", {}).setdefault(clave_rec, {})

                default_lim = 0 if sub_lim == "min" else 100
                if recursos_definicion and clave_rec in recursos_definicion:
                    default_lim = recursos_definicion[clave_rec].get(sub_lim, default_lim)

                actual_lim = float(lim_dict.get(sub_lim, default_lim))
                nuevo_lim = int(round(_aplicar_operacion_matematica(actual_lim, op_mat, valor_num)))
                lim_dict[sub_lim] = nuevo_lim

                # Reclamping inmediato del recurso si quedó fuera del rango
                recursos = run_data.setdefault("recursos", {})
                if clave_rec in recursos:
                    res_val = float(recursos[clave_rec])
                    cur_min = float(lim_dict.get("min", recursos_definicion.get(clave_rec, {}).get("min", 0) if recursos_definicion else 0))
                    cur_max = float(lim_dict.get("max", recursos_definicion.get(clave_rec, {}).get("max", 100) if recursos_definicion else 100))
                    recursos[clave_rec] = int(max(cur_min, min(cur_max, res_val)))

        # C) Afinidad: 'afinidad.<target>'
        elif ruta.startswith("afinidad."):
            target = ruta.split(".", 1)[1]
            if target in ("portador", "self", "me") and duenio_id:
                target = duenio_id
            if target:
                afinidades = run_data.setdefault("afinidad", {})
                actual_af = float(afinidades.get(target, 50))
                nueva_af = _aplicar_operacion_matematica(actual_af, op_mat, valor_num)
                afinidades[target] = max(0, min(100, int(round(nueva_af))))

        # D) Variables arbitrarias del universo: 'variables.<clave>'
        elif ruta.startswith("variables."):
            var_clave = ruta.split(".", 1)[1]
            variables = run_data.setdefault("variables", {})
            actual_var = float(variables.get(var_clave, 0.0))
            nueva_var = _aplicar_operacion_matematica(actual_var, op_mat, valor_num)
            variables[var_clave] = round(nueva_var, 4)



def _frecuencia_coincide(
    efecto: EfectoSchema,
    disparador: Any,
    run_data: Dict[str, Any],
    duenio_id: Optional[str] = None,
    mes_actual: Optional[int] = None,
    catalogo_frecuencias: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Determina si un efecto debe ejecutarse según el disparador del motor,
    evaluando si es 'al_obtener' o una periodicidad relativa calculada
    desde el mes de adquisición de la carta/personaje.
    """
    disp_valor = disparador.value if hasattr(disparador, "value") else str(disparador)

    # Coincidencia directa por disparador legacy
    if efecto.disparador:
        leg_disp = efecto.disparador.value if hasattr(efecto.disparador, "value") else str(efecto.disparador)
        if leg_disp == disp_valor:
            return True

    frec_id = efecto.frecuencia_id
    if not frec_id:
        return False

    # 1. Disparador AL_OBTENER
    if disp_valor == "al_obtener":
        if frec_id == "al_obtener":
            return True
        if catalogo_frecuencias and frec_id in catalogo_frecuencias:
            return catalogo_frecuencias[frec_id].get("evento_motor") == "al_obtener"
        return False

    # 2. Disparador CADA_MES / INICIO_MES
    if disp_valor in ("cada_mes", "inicio_mes"):
        if frec_id in ("cada_mes", "mensual"):
            return True

        if catalogo_frecuencias and frec_id in catalogo_frecuencias:
            frec_item = catalogo_frecuencias[frec_id]
            if frec_item.get("evento_motor") != "inicio_mes":
                return False

            cada = int(frec_item.get("cada", 1))
            desfase = int(frec_item.get("desfase", 0))
            conteo_desde = frec_item.get("conteo_desde", "adquisicion")

            cur_mes = mes_actual or run_data.get("mes_actual", 1)

            if conteo_desde == "adquisicion" and duenio_id:
                adqs = run_data.get("adquisiciones", {})
                mes_adq = adqs.get(duenio_id, {}).get("mes", 1)
                delta = cur_mes - mes_adq
                # Dispara si pasó al menos 1 mes desde la adquisición y cumple el intervalo
                return delta > 0 and (delta - desfase) >= 0 and ((delta - desfase) % cada == 0)
            else:
                return (cur_mes - desfase) > 0 and ((cur_mes - desfase) % cada == 0)

    return False


def despachar_efectos(
    disparador: Any,
    run_data: Dict[str, Any],
    efectos: List[Any],
    recursos_definicion: Optional[Dict[str, Dict[str, Any]]] = None,
    duenio_id: Optional[str] = None,
    mes_actual: Optional[int] = None,
    catalogo_acciones: Optional[Dict[str, Any]] = None,
    catalogo_frecuencias: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Filtra los efectos por el disparador solicitado, evalúa sus condiciones
    y ejecuta las acciones correspondientes mutando run_data.
    Soporta lista de acciones ordenadas y cálculo de periodicidad relativa.
    """
    for efecto_raw in efectos:
        if isinstance(efecto_raw, dict):
            efecto = EfectoSchema(**efecto_raw)
        else:
            efecto = efecto_raw

        if _frecuencia_coincide(
            efecto, disparador, run_data, duenio_id, mes_actual, catalogo_frecuencias
        ):
            if evaluar_condiciones(efecto.condiciones, run_data):
                # Ejecutar lista ordenada de acciones desacopladas
                if efecto.acciones:
                    for accion in efecto.acciones:
                        ejecutar_accion(
                            accion,
                            run_data,
                            recursos_definicion,
                            duenio_id=duenio_id,
                            catalogo_acciones=catalogo_acciones,
                        )
                # Fallback legacy si viniera únicamente `accion`
                elif efecto.accion:
                    ejecutar_accion(
                        efecto.accion,
                        run_data,
                        recursos_definicion,
                        duenio_id=duenio_id,
                        catalogo_acciones=catalogo_acciones,
                    )
