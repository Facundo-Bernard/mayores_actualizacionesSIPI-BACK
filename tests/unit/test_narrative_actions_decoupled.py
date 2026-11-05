import pytest
from app.features.narrative.enums import DisparadorEnum, TipoCondicionEnum, OperadorEnum, TipoCalculoEnum
from app.features.narrative.schemas.rules_schemas import (
    EfectoSchema,
    CondicionSchema,
    AccionReferenciadaSchema,
    ParametrosAccionSchema,
    PrimitivaOperacionEnum,
)
from app.features.narrative.engine.rule_engine import (
    ejecutar_accion,
    despachar_efectos,
    evaluar_condiciones,
)


def test_ejecutar_accion_modificar_recurso_fijo_y_clamping():
    run_data = {"recursos": {"pueblo": 40}}
    recursos_def = {"pueblo": {"min": 0, "max": 100}}

    accion = AccionReferenciadaSchema(
        accion_id="modificar_recurso",
        parametros=ParametrosAccionSchema(
            clave="pueblo",
            valor=20,
            tipo_calculo=TipoCalculoEnum.FIJO,
        ),
    )
    ejecutar_accion(accion, run_data, recursos_def)
    assert run_data["recursos"]["pueblo"] == 60

    # Reducir sobrepasando el mínimo permitido
    accion_resta = AccionReferenciadaSchema(
        accion_id="modificar_recurso",
        parametros=ParametrosAccionSchema(
            clave="pueblo",
            valor=-80,
            tipo_calculo=TipoCalculoEnum.FIJO,
        ),
    )
    ejecutar_accion(accion_resta, run_data, recursos_def)
    assert run_data["recursos"]["pueblo"] == 0


def test_ejecutar_accion_amortiguar_danio():
    run_data = {
        "recursos": {"oro": 100},
        "modificadores_pasivos": [],
    }
    recursos_def = {"oro": {"min": 0, "max": 200}}

    # 1. Aplicar pasivo que amortigua 50% de daño en "oro"
    accion_amortiguar = AccionReferenciadaSchema(
        accion_id="amortiguar_danio",
        parametros=ParametrosAccionSchema(clave="oro", valor=50),
    )
    ejecutar_accion(accion_amortiguar, run_data, recursos_def, duenio_id="escudo_oro")
    assert len(run_data["modificadores_pasivos"]) == 1
    assert run_data["modificadores_pasivos"][0]["reduccion_porcentual"] == 50

    # 2. Restar 40 de oro -> amortiguado al 50% = resta solo 20
    accion_dano = AccionReferenciadaSchema(
        accion_id="modificar_recurso",
        parametros=ParametrosAccionSchema(clave="oro", valor=-40),
    )
    ejecutar_accion(accion_dano, run_data, recursos_def)
    assert run_data["recursos"]["oro"] == 80  # 100 - 20


def test_ejecutar_accion_modificar_afinidad_portador():
    run_data = {"afinidad": {"canciller_heinz": 50}}

    accion = AccionReferenciadaSchema(
        accion_id="modificar_afinidad",
        parametros=ParametrosAccionSchema(
            destino="portador",
            valor=15,
        ),
    )
    ejecutar_accion(accion, run_data, duenio_id="canciller_heinz")
    assert run_data["afinidad"]["canciller_heinz"] == 65


def test_ejecutar_accion_otorgar_y_remover_tag():
    run_data = {"tags_activos": []}

    accion_add = AccionReferenciadaSchema(
        accion_id="otorgar_tag",
        parametros=ParametrosAccionSchema(tag="bendicion_real"),
    )
    ejecutar_accion(accion_add, run_data)
    assert "bendicion_real" in run_data["tags_activos"]

    # Agregar duplicado no debe crear duplicados
    ejecutar_accion(accion_add, run_data)
    assert run_data["tags_activos"].count("bendicion_real") == 1

    # Remover tag
    accion_del = AccionReferenciadaSchema(
        accion_id="remover_tag",
        parametros=ParametrosAccionSchema(tag="bendicion_real"),
    )
    ejecutar_accion(accion_del, run_data)
    assert "bendicion_real" not in run_data["tags_activos"]


def test_despachar_efectos_acciones_multiples_en_orden():
    run_data = {
        "recursos": {"pueblo": 50, "nobleza": 50},
        "tags_activos": [],
    }
    efecto = EfectoSchema(
        frecuencia_id="al_obtener",
        condiciones=[
            CondicionSchema(
                tipo=TipoCondicionEnum.COMPARAR_RECURSO,
                clave="pueblo",
                operador=OperadorEnum.MAYOR_IGUAL,
                valor=40,
            )
        ],
        acciones=[
            AccionReferenciadaSchema(
                accion_id="modificar_recurso",
                parametros=ParametrosAccionSchema(clave="pueblo", valor=-20),
            ),
            AccionReferenciadaSchema(
                accion_id="modificar_recurso",
                parametros=ParametrosAccionSchema(clave="nobleza", valor=10),
            ),
            AccionReferenciadaSchema(
                accion_id="otorgar_tag",
                parametros=ParametrosAccionSchema(tag="reforma_aprobada"),
            ),
        ],
    )

    despachar_efectos("al_obtener", run_data, [efecto])
    assert run_data["recursos"]["pueblo"] == 30
    assert run_data["recursos"]["nobleza"] == 60
    assert "reforma_aprobada" in run_data["tags_activos"]


def test_despachar_efectos_frecuencia_relativa_desde_adquisicion():
    # Supongamos que una carta se obtuvo en el mes 2
    # y tiene una frecuencia de disparo 'cada_2_meses' desde su adquisición
    run_data = {
        "mes_actual": 4,
        "recursos": {"oro": 100},
        "adquisiciones": {
            "carta_mina": {"mes": 2, "tipo": "carta"},
        },
    }
    catalogo_frecuencias = {
        "cada_2_meses": {
            "id": "cada_2_meses",
            "evento_motor": "inicio_mes",
            "cada": 2,
            "desfase": 0,
            "conteo_desde": "adquisicion",
            "activo": True,
        }
    }
    efecto = EfectoSchema(
        frecuencia_id="cada_2_meses",
        acciones=[
            AccionReferenciadaSchema(
                accion_id="modificar_recurso",
                parametros=ParametrosAccionSchema(clave="oro", valor=25),
            )
        ],
    )

    # Mes 3: delta = 3 - 2 = 1 -> 1 % 2 != 0 -> no debe disparar
    run_data["mes_actual"] = 3
    despachar_efectos(
        "inicio_mes",
        run_data,
        [efecto],
        duenio_id="carta_mina",
        mes_actual=3,
        catalogo_frecuencias=catalogo_frecuencias,
    )
    assert run_data["recursos"]["oro"] == 100

    # Mes 4: delta = 4 - 2 = 2 -> 2 % 2 == 0 -> debe disparar
    run_data["mes_actual"] = 4
    despachar_efectos(
        "inicio_mes",
        run_data,
        [efecto],
        duenio_id="carta_mina",
        mes_actual=4,
        catalogo_frecuencias=catalogo_frecuencias,
    )
    assert run_data["recursos"]["oro"] == 125


def test_mutar_estado_operaciones_matematicas():
    from app.features.narrative.enums import OperacionMatematicaEnum
    run_data = {"recursos": {"oro": 100}}

    # 1. Multiplicar: 100 * 1.5 = 150
    accion_mul = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="recursos.oro",
            operacion_matematica=OperacionMatematicaEnum.MULTIPLICAR,
            valor=1.5,
        ),
    )
    ejecutar_accion(accion_mul, run_data)
    assert run_data["recursos"]["oro"] == 150

    # 2. Dividir: 150 / 3 = 50
    accion_div = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="recursos.oro",
            operacion_matematica=OperacionMatematicaEnum.DIVIDIR,
            valor=3,
        ),
    )
    ejecutar_accion(accion_div, run_data)
    assert run_data["recursos"]["oro"] == 50

    # 3. División por cero: mantiene 50
    accion_div_cero = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="recursos.oro",
            operacion_matematica=OperacionMatematicaEnum.DIVIDIR,
            valor=0,
        ),
    )
    ejecutar_accion(accion_div_cero, run_data)
    assert run_data["recursos"]["oro"] == 50

    # 4. Porcentual: 50 + 20% = 60
    accion_pct = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="recursos.oro",
            operacion_matematica=OperacionMatematicaEnum.PORCENTUAL,
            valor=20,
        ),
    )
    ejecutar_accion(accion_pct, run_data)
    assert run_data["recursos"]["oro"] == 60

    # 5. Fijar: 60 -> 77
    accion_fijar = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="recursos.oro",
            operacion_matematica=OperacionMatematicaEnum.FIJAR,
            valor=77,
        ),
    )
    ejecutar_accion(accion_fijar, run_data)
    assert run_data["recursos"]["oro"] == 77


def test_mutar_estado_limites_dinamicos():
    from app.features.narrative.enums import OperacionMatematicaEnum
    run_data = {
        "recursos": {"oro": 100},
        "limites": {"oro": {"min": 0, "max": 120}},
    }

    # Reducir el límite máximo a 80 -> el recurso actual (100) debe ajustarse a 80 inmediatamente
    accion_max = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="limites.oro.max",
            operacion_matematica=OperacionMatematicaEnum.FIJAR,
            valor=80,
        ),
    )
    ejecutar_accion(accion_max, run_data)
    assert run_data["limites"]["oro"]["max"] == 80
    assert run_data["recursos"]["oro"] == 80

    # Subir el límite mínimo a 50
    accion_min = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="limites.oro.min",
            operacion_matematica=OperacionMatematicaEnum.FIJAR,
            valor=50,
        ),
    )
    ejecutar_accion(accion_min, run_data)
    assert run_data["limites"]["oro"]["min"] == 50


def test_mutar_estado_afinidad_y_variables():
    from app.features.narrative.enums import OperacionMatematicaEnum
    run_data = {
        "afinidad": {"pj_canciller": 40},
        "variables": {},
    }

    # Afinidad portador
    accion_af = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="afinidad.portador",
            operacion_matematica=OperacionMatematicaEnum.SUMAR,
            valor=25,
        ),
    )
    ejecutar_accion(accion_af, run_data, duenio_id="pj_canciller")
    assert run_data["afinidad"]["pj_canciller"] == 65

    # Variable personalizada
    accion_var = AccionReferenciadaSchema(
        accion_id="mutar_estado",
        parametros=ParametrosAccionSchema(
            ruta="variables.inflacion",
            operacion_matematica=OperacionMatematicaEnum.SUMAR,
            valor=12.5,
        ),
    )
    ejecutar_accion(accion_var, run_data)
    assert run_data["variables"]["inflacion"] == 12.5


def test_condiciones_aparicion_evaluacion():
    run_data = {
        "recursos": {"oro": 100},
        "tags_activos": ["nobles_aliados"],
        "afinidad": {"pj_canciller": 80},
    }

    # Carta 1: Requiere oro >= 50 (cumple)
    cond_oro = CondicionSchema(
        tipo=TipoCondicionEnum.COMPARAR_RECURSO,
        clave="oro",
        operador=OperadorEnum.MAYOR_IGUAL,
        valor=50,
    )
    assert evaluar_condiciones([cond_oro], run_data) is True

    # Carta 2: Requiere tag 'plebeyos_rebeldes' (no cumple)
    cond_tag = CondicionSchema(
        tipo=TipoCondicionEnum.TIENE_TAG,
        tag="plebeyos_rebeldes",
    )
    assert evaluar_condiciones([cond_tag], run_data) is False
