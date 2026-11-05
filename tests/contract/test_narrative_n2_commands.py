"""N2: comandos idempotentes, recibos embebidos y cierre económico durable."""

import asyncio
from datetime import datetime, timezone

import pytest
from bson import BSON
from pymongo.errors import ConnectionFailure

from app.features.narrative.constants import (
    COLL_RUNS,
    PROTOCOLO_V3,
)
from app.features.narrative.game import command_coordinator
from app.features.narrative.game.command_coordinator import (
    CommandResolution,
    ejecutar_comando,
)
from app.features.narrative.game.command_protocol import (
    CommandError,
    CommandOutcomeUnknown,
    Principal,
    hash_comando,
)
from app.features.narrative.game.command_receipts import (
    obtener_recibo_autorizado,
    obtener_snapshot_autorizado,
)
from app.features.narrative.game.economy_obligation import (
    ESTADO_LIQUIDADA,
    ESTADO_LOCAL,
    ESTADO_PENDIENTE,
    aplicar_liquidacion,
    reconciliar_liquidaciones_pendientes,
)
from app.features.narrative.game.run_repository import persistir_run
from app.features.narrative.schemas.v3_contract_schemas import (
    AvanzarNodoCommand,
    AvanzarNodoPayload,
)
from app.shared.economy_points import obtener_puntos_por_calificacion

pytestmark = pytest.mark.contract

FECHA = "2099-06-01"


def _run_id(user_id: int) -> str:
    return f"run_v3_{user_id}_{FECHA}"


def _run(user_id: int, **extra) -> dict:
    doc = {
        "_id": _run_id(user_id),
        "protocolo": PROTOCOLO_V3,
        "user_id": user_id,
        "guest_id": None,
        "date": FECHA,
        "game_id": "narrativo",
        "generation": 1,
        "version": 0,
        "status": "in_progress",
        "fase_actual": "TOMA_DECISION_EVENTO",
        "mes_actual": 1,
        "motor": "v2",
        "recursos": {"oro": 50},
        "finalizacion": {"rango": "S"},
        "recibos": [],
        "updated_at": datetime.now(timezone.utc),
    }
    doc.update(extra)
    return doc


def _cmd(command_id: str = "cmd_1", expected_version: int = 0, opcion: str = "op_1", generation: int = 1):
    return AvanzarNodoCommand(
        commandId=command_id,
        generation=generation,
        expectedVersion=expected_version,
        type="AVANZAR_NODO",
        payload=AvanzarNodoPayload(opcionId=opcion),
    )


def _resolver_avance(run, comando):
    return CommandResolution(
        cambios={"mes_actual": 2, "fase_actual": "BALANCE_MES"},
        consecuencias=[{"consecuenciaId": "c_1", "tipo": "recurso"}],
        resultado={"resultadoId": "r_1", "texto": "Avanzó"},
    )


def _resolver_cierre(run, comando):
    return CommandResolution(
        cambios={
            "status": "completed",
            "fase_actual": "FINALIZADA",
            "mes_actual": 12,
            "finalizacion": {"rango": "S"},
        },
        resultado={"resultadoId": "r_fin", "texto": "Fin"},
    )


def _resolver_derrota(run, comando):
    return CommandResolution(
        cambios={
            "status": "game_over",
            "fase_actual": "FINALIZADA",
            "mes_actual": 5,
            "finalizacion": {"rango": "F"},
        },
        resultado={"resultadoId": "r_derrota", "texto": "Derrota"},
    )


async def _sembrar(test_db, cleanup, user_id: int, **extra) -> dict:
    run = _run(user_id, **extra)
    await test_db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})
    return run


async def _run_actual(test_db, user_id: int) -> dict:
    return await test_db[COLL_RUNS].find_one({"_id": _run_id(user_id)})


@pytest.mark.asyncio
async def test_confirma_una_version_y_recupera_recibo(test_db, cleanup, seeded_user):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    respuesta = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_avance, principal=principal
    )
    assert respuesta["version"] == 1
    assert respuesta["previousVersion"] == 0
    assert respuesta["puntos_ganados"] == 0
    assert respuesta["estado"]["mes_actual"] == 2
    assert respuesta["recompensa"] is None

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1

    # Mismo commandId con la versión vieja: el recibo se recupera antes de validar versión.
    repetido = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_avance, principal=principal
    )
    assert repetido["version"] == 1
    assert repetido["resultado"] == respuesta["resultado"]
    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1

    recibo = await obtener_recibo_autorizado(
        _run_id(user_id), "cmd_1", generation=1, principal=principal
    )
    assert recibo["runId"] == _run_id(user_id)
    assert recibo["commandId"] == "cmd_1"

    snapshot = await obtener_snapshot_autorizado(
        _run_id(user_id), generation=1, principal=principal
    )
    assert snapshot["version"] == 1
    assert snapshot["estado"]["mes_actual"] == 2


@pytest.mark.asyncio
async def test_mismo_command_id_con_otro_payload_no_muta(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    await ejecutar_comando(_run_id(user_id), _cmd(), _resolver_avance, principal=principal)

    with pytest.raises(CommandError) as exc:
        await ejecutar_comando(
            _run_id(user_id),
            _cmd(opcion="op_2"),
            _resolver_avance,
            principal=principal,
        )
    assert exc.value.code == "command_reused"

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1


@pytest.mark.asyncio
async def test_version_vieja_no_publica_resolucion(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    await ejecutar_comando(_run_id(user_id), _cmd(), _resolver_avance, principal=principal)

    with pytest.raises(CommandError) as exc:
        await ejecutar_comando(
            _run_id(user_id),
            _cmd(command_id="cmd_2", expected_version=0),
            _resolver_avance,
            principal=principal,
        )
    assert exc.value.code == "version_conflict"
    assert exc.value.detail["currentVersion"] == 1

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert [r["commandId"] for r in actual["recibos"]] == ["cmd_1"]


@pytest.mark.asyncio
async def test_mismo_comando_simultaneo_una_confirmacion(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    respuestas = await asyncio.gather(
        *[
            ejecutar_comando(
                _run_id(user_id), _cmd(), _resolver_avance, principal=principal
            )
            for _ in range(6)
        ]
    )

    assert {r["version"] for r in respuestas} == {1}
    assert {tuple(sorted(r["resultado"].items())) for r in respuestas} == {
        (("resultadoId", "r_1"), ("texto", "Avanzó"))
    }
    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1


@pytest.mark.asyncio
async def test_cada_version_tiene_recibo_y_el_documento_sigue_acotado(
    test_db, cleanup, seeded_user
):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    for numero in range(1, 13):
        await ejecutar_comando(
            _run_id(user_id),
            _cmd(command_id=f"cmd_{numero}", expected_version=numero - 1),
            _resolver_avance,
            principal=principal,
        )

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 12
    assert [r["version"] for r in actual["recibos"]] == list(range(1, 13))
    assert len(BSON.encode(actual)) < 2_000_000


@pytest.mark.asyncio
async def test_dos_command_ids_simultaneos_una_sola_version(
    test_db, cleanup, seeded_user
):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    resultados = await asyncio.gather(
        ejecutar_comando(
            _run_id(user_id),
            _cmd(command_id="cmd_a", opcion="op_a"),
            _resolver_avance,
            principal=principal,
        ),
        ejecutar_comando(
            _run_id(user_id),
            _cmd(command_id="cmd_b", opcion="op_b"),
            _resolver_avance,
            principal=principal,
        ),
        return_exceptions=True,
    )

    exitos = [r for r in resultados if isinstance(r, dict)]
    errores = [r for r in resultados if isinstance(r, CommandError)]
    assert len(exitos) == 1
    assert len(errores) == 1
    assert errores[0].code == "version_conflict"

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1


@pytest.mark.asyncio
async def test_propiedad_y_generacion(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)

    with pytest.raises(CommandError) as exc:
        await ejecutar_comando(
            _run_id(user_id), _cmd(), _resolver_avance, principal=Principal(user_id + 1)
        )
    assert exc.value.code == "forbidden"

    with pytest.raises(CommandError) as exc:
        await ejecutar_comando(
            _run_id(user_id),
            _cmd(generation=2),
            _resolver_avance,
            principal=Principal(user_id),
        )
    assert exc.value.code == "generation_conflict"

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 0
    assert actual["recibos"] == []


@pytest.mark.asyncio
async def test_fallo_del_resolver_no_muta(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)

    def _falla(run, comando):
        raise RuntimeError("contenido roto")

    with pytest.raises(RuntimeError):
        await ejecutar_comando(
            _run_id(user_id), _cmd(), _falla, principal=Principal(user_id)
        )

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 0
    assert actual["recibos"] == []


@pytest.mark.asyncio
async def test_commit_incierto_se_recupera_con_la_misma_clave(
    test_db, cleanup, seeded_user, monkeypatch
):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    real = command_coordinator.confirmar_comando
    llamadas = {"n": 0}

    async def _confirma_y_pierde_respuesta(*args, **kwargs):
        confirmado = await real(*args, **kwargs)
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise ConnectionFailure("respuesta perdida después del commit")
        return confirmado

    monkeypatch.setattr(
        command_coordinator, "confirmar_comando", _confirma_y_pierde_respuesta
    )

    with pytest.raises(CommandOutcomeUnknown) as exc:
        await ejecutar_comando(
            _run_id(user_id), _cmd(), _resolver_avance, principal=principal
        )
    assert exc.value.retryable is True

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1

    recuperado = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_avance, principal=principal
    )
    assert recuperado["version"] == 1
    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 1
    assert len(actual["recibos"]) == 1


@pytest.mark.asyncio
async def test_cierre_embebe_obligacion_y_acredita_una_vez(
    test_db, cleanup, seeded_user
):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)
    esperado = int((await obtener_puntos_por_calificacion())["S"])

    respuesta = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_cierre, principal=principal
    )

    assert respuesta["estado"]["status"] == "completed"
    assert respuesta["puntos_ganados"] == esperado
    assert respuesta["recompensa"]["puntos"] == esperado
    assert respuesta["recompensa"]["canal"] == "ledger"
    assert respuesta["recompensa"]["liquidacion"]["estado"] == ESTADO_LIQUIDADA

    actual = await _run_actual(test_db, user_id)
    assert actual["liquidacion"]["estado"] == ESTADO_LIQUIDADA
    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado

    repetido = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_cierre, principal=principal
    )
    assert repetido["puntos_ganados"] == 0
    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado
    assert (
        await test_db["economy_ledger"].count_documents(
            {"_id": f"attempt:{user_id}:narrativo:{FECHA}:normal"}
        )
        == 1
    )


@pytest.mark.asyncio
async def test_cierre_sin_asiento_se_repara_y_no_dobla(
    test_db, cleanup, seeded_user
):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    esperado = int((await obtener_puntos_por_calificacion())["S"])

    await ejecutar_comando(
        _run_id(user_id),
        _cmd(),
        _resolver_cierre,
        principal=Principal(user_id),
        aplicar_economia=False,
    )

    actual = await _run_actual(test_db, user_id)
    assert actual["liquidacion"]["estado"] == ESTADO_PENDIENTE
    assert (await test_db["usuarios"].find_one({"id": user_id}))["puntos"] == 0

    pendientes = await reconciliar_liquidaciones_pendientes(older_than_seconds=0)
    assert pendientes == 1
    actual = await _run_actual(test_db, user_id)
    assert actual["liquidacion"]["estado"] == ESTADO_LIQUIDADA
    assert (await test_db["usuarios"].find_one({"id": user_id}))["puntos"] == esperado

    # Simula caída después del crédito y antes de marcar la obligación.
    await test_db[COLL_RUNS].update_one(
        {"_id": _run_id(user_id)},
        {"$set": {"liquidacion.estado": ESTADO_PENDIENTE}},
    )
    assert await reconciliar_liquidaciones_pendientes(older_than_seconds=0) == 1

    actual = await _run_actual(test_db, user_id)
    assert actual["liquidacion"]["estado"] == ESTADO_LIQUIDADA
    assert (await test_db["usuarios"].find_one({"id": user_id}))["puntos"] == esperado


@pytest.mark.asyncio
async def test_derrota_registra_intento_sin_acreditar(test_db, cleanup, seeded_user):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)

    respuesta = await ejecutar_comando(
        _run_id(user_id), _cmd(), _resolver_derrota, principal=Principal(user_id)
    )
    assert respuesta["puntos_ganados"] == 0
    assert respuesta["recompensa"]["puntos"] == 0
    assert respuesta["recompensa"]["liquidacion"]["estado"] == ESTADO_LIQUIDADA

    intento = await test_db["user_attempts"].find_one(
        {"user_id": user_id, "game_id": "narrativo", "date": FECHA}
    )
    assert intento["status"] == "failed"
    assert (await test_db["usuarios"].find_one({"id": user_id}))["puntos"] == 0


@pytest.mark.asyncio
async def test_invitado_liquida_local_una_sola_vez(test_db, cleanup):
    user_id = -913001
    guest_id = "invitado-n2-01"
    run = await _sembrar(test_db, cleanup, user_id, guest_id=guest_id)
    principal = Principal(user_id, guest_id)
    esperado = int((await obtener_puntos_por_calificacion())["S"])
    clave = f"guest_narrative:{guest_id}:narrativo:{FECHA}"
    cleanup.add("economy_ledger", {"_id": clave})

    respuesta = await ejecutar_comando(
        run["_id"], _cmd(), _resolver_cierre, principal=principal
    )
    assert respuesta["puntos_ganados"] == esperado
    assert respuesta["recompensa"]["canal"] == "local"
    assert "liquidacion" not in respuesta["recompensa"]

    actual = await _run_actual(test_db, user_id)
    assert actual["liquidacion"]["estado"] == ESTADO_LOCAL
    auditoria = await test_db["economy_ledger"].find_one({"_id": clave})
    assert auditoria["status"] == "recorded"
    assert auditoria["puntos"] == esperado

    repetido = await ejecutar_comando(
        run["_id"], _cmd(), _resolver_cierre, principal=principal
    )
    assert repetido["puntos_ganados"] == 0
    assert (
        await test_db["economy_ledger"].count_documents({"_id": clave}) == 1
    )


@pytest.mark.asyncio
async def test_legacy_no_muta_run_v3(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    run = await _sembrar(test_db, cleanup, user_id)

    with pytest.raises(Exception) as exc:
        await persistir_run(run)
    assert getattr(exc.value, "status_code", None) == 409

    actual = await _run_actual(test_db, user_id)
    assert actual["version"] == 0


@pytest.mark.asyncio
async def test_lectura_recibo_ausente_y_ajeno(test_db, cleanup, seeded_user):
    user = await seeded_user()
    user_id = user["id"]
    await _sembrar(test_db, cleanup, user_id)
    principal = Principal(user_id)

    with pytest.raises(CommandError) as exc:
        await obtener_recibo_autorizado(
            _run_id(user_id), "no_existe", generation=1, principal=principal
        )
    assert exc.value.code == "receipt_not_found"
    assert exc.value.retryable is True

    with pytest.raises(CommandError) as exc:
        await obtener_snapshot_autorizado(
            _run_id(user_id), generation=1, principal=Principal(user_id + 1)
        )
    assert exc.value.code == "forbidden"


def test_hash_canonico_discrimina_contenido():
    base = _cmd()
    mismo = _cmd()
    otra_opcion = _cmd(opcion="op_2")
    otra_version = _cmd(expected_version=1)

    assert hash_comando(base) == hash_comando(mismo)
    assert hash_comando(base) != hash_comando(otra_opcion)
    assert hash_comando(base) != hash_comando(otra_version)
    assert hash_comando(base) == hash_comando(base)


def test_tope_de_tamano_rechaza_antes_de_confirmar():
    with pytest.raises(CommandError) as exc:
        command_coordinator._verificar_tamano(
            {"_id": "run_tope", "historial": "x" * command_coordinator.TAMANO_MAXIMO_RUN},
            {"commandId": "cmd_tope"},
            None,
        )

    assert exc.value.code == "phase_conflict"

