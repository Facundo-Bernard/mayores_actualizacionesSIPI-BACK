"""Acreditación de puntos del narrativo para cuentas e invitados (D4/D6)."""

import pytest

from app.features.narrative.constants import COLL_RUNS, COLL_USER_ATTEMPTS
from app.features.narrative.game.endings_service import sincronizar_intento_usuario
from app.shared.economy_points import obtener_puntos_por_calificacion

pytestmark = pytest.mark.contract

DATE = "2099-05-15"


def _run(user_id: int, *, status: str = "completed", rango: str = "S", **extra) -> dict:
    run = {
        "_id": f"run_puntos_{user_id}_{DATE}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "status": status,
        "mes_actual": 12 if status == "completed" else 4,
        "finalizacion": {"rango": rango, "tipo": "victoria_tiempo"},
        "recursos": {"oro": 40},
    }
    run.update(extra)
    return run


async def _puntos_por_rango(rango: str) -> int:
    return int((await obtener_puntos_por_calificacion())[rango])


@pytest.mark.asyncio
async def test_cuenta_acredita_puntos_una_sola_vez(test_db, cleanup, seeded_user):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    esperado = await _puntos_por_rango("S")
    run = _run(user_id)

    ganados = await sincronizar_intento_usuario(run)
    assert ganados == esperado

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado

    intento = await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": user_id, "date": DATE})
    assert intento["status"] == "completed"
    assert intento["grade"] == "S"
    assert intento["difficulty"] == "normal"

    asiento = await test_db["economy_ledger"].find_one(
        {"_id": f"attempt:{user_id}:narrativo:{DATE}:normal"}
    )
    assert asiento["status"] == "applied"
    assert asiento["puntos"] == esperado

    replay = await sincronizar_intento_usuario(run)
    assert replay == 0
    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado


@pytest.mark.asyncio
async def test_derrota_no_acredita_ni_consume_clave(test_db, cleanup, seeded_user):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    run = _run(user_id, status="game_over", rango="F")

    ganados = await sincronizar_intento_usuario(run)
    assert ganados == 0

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == 0
    assert await test_db["economy_ledger"].find_one({"_id": f"attempt:{user_id}:narrativo:{DATE}:normal"}) is None

    intento = await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": user_id, "date": DATE})
    assert intento["status"] == "failed"
    assert intento["score"] == 0
    assert intento["stars"] == 0


@pytest.mark.asyncio
async def test_intento_narrativo_usa_catalogo_editable_del_panel(
    test_db, cleanup, seeded_user
):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    await test_db["configuracion_economia"].replace_one(
        {"_id": "global_economy"},
        {"puntos_por_calificacion": {"S": 123, "A": 90, "B": 75, "C": 50, "F": 0}},
        upsert=True,
    )
    cleanup.add("configuracion_economia", {"_id": "global_economy"})

    assert await sincronizar_intento_usuario(_run(user_id, rango="S")) == 123

    intento = await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": user_id, "date": DATE})
    assert intento["score"] == 123
    assert intento["stars"] == 3


@pytest.mark.asyncio
async def test_reinicio_no_degrada_intento_completado(test_db, cleanup, seeded_user):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    esperado = await _puntos_por_rango("S")

    assert await sincronizar_intento_usuario(_run(user_id, rango="S")) == esperado

    derrota_generacion_2 = _run(user_id, status="game_over", rango="F")
    derrota_generacion_2["generation"] = 2
    assert await sincronizar_intento_usuario(derrota_generacion_2) == 0

    intento = await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": user_id, "date": DATE})
    assert intento["status"] == "completed"
    assert intento["grade"] == "S"
    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado


@pytest.mark.asyncio
async def test_completado_posterior_reemplaza_derrota_sin_doblar_puntos(
    test_db, cleanup, seeded_user
):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    esperado = await _puntos_por_rango("A")

    assert await sincronizar_intento_usuario(_run(user_id, status="game_over", rango="F")) == 0
    assert await sincronizar_intento_usuario(_run(user_id, rango="A")) == esperado

    intento = await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": user_id, "date": DATE})
    assert intento["status"] == "completed"
    assert intento["grade"] == "A"
    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado


@pytest.mark.asyncio
async def test_invitado_recibe_puntos_sin_tocar_cuenta(test_db, cleanup):
    guest_id = "invitado-puntos-01"
    interno = -912345
    esperado = await _puntos_por_rango("A")
    run = _run(interno, rango="A", guest_id=guest_id)
    clave = f"guest_narrative:{guest_id}:narrativo:{DATE}"

    cleanup.add("economy_ledger", {"_id": clave})
    cleanup.add(COLL_USER_ATTEMPTS, {"user_id": interno})
    cleanup.add("usuarios", {"id": interno})

    ganados = await sincronizar_intento_usuario(run)
    assert ganados == esperado

    assert await test_db["usuarios"].find_one({"id": interno}) is None
    assert await test_db[COLL_USER_ATTEMPTS].find_one({"user_id": interno}) is None

    auditoria = await test_db["economy_ledger"].find_one({"_id": clave})
    assert auditoria["motivo"] == "guest_narrative"
    assert auditoria["status"] == "recorded"
    assert auditoria["puntos"] == esperado
    assert auditoria["metadata"]["guest_id"] == guest_id

    repetido = await sincronizar_intento_usuario(run)
    assert repetido == 0


@pytest.mark.asyncio
async def test_invitado_derrotado_no_gana_puntos(test_db, cleanup):
    guest_id = "invitado-derrota-01"
    interno = -912346
    cleanup.add("economy_ledger", {"_id": f"guest_narrative:{guest_id}:narrativo:{DATE}"})
    run = _run(interno, status="game_over", rango="C", guest_id=guest_id)

    assert await sincronizar_intento_usuario(run) == 0
    assert await test_db["economy_ledger"].find_one(
        {"_id": f"guest_narrative:{guest_id}:narrativo:{DATE}"}
    ) is None


@pytest.mark.asyncio
async def test_victoria_v2_expone_puntos_ganados(
    client, test_db, cleanup, make_token, seeded_user
):
    user = await seeded_user(puntos=0)
    user_id = user["id"]
    esperado = await _puntos_por_rango("S")
    run = {
        "_id": f"run_puntos_{user_id}_{DATE}",
        "user_id": user_id,
        "date": DATE,
        "game_id": "narrativo",
        "universo_id": "universo_puntos",
        "motor": "v2",
        "mes_actual": 12,
        "fase_actual": "BALANCE_MES",
        "status": "in_progress",
        "recursos": {"oro": 90, "pueblo": 90, "ejercito": 90, "fe": 90},
        "afinidad": {},
        "cartas_en_mano": [],
        "tags_activos": [],
        "turno_actual": {},
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "historial_mensual": [],
    }
    await test_db[COLL_RUNS].replace_one({"_id": run["_id"]}, run, upsert=True)
    cleanup.add(COLL_RUNS, {"_id": run["_id"]})

    respuesta = await client.post(
        "/api/narrative/v2/partida/avanzar-mes",
        json={"date": DATE},
        headers={"Authorization": f"Bearer {make_token(user_id)}"},
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "completed"
    assert cuerpo["puntos_ganados"] == esperado

    usuario = await test_db["usuarios"].find_one({"id": user_id})
    assert usuario["puntos"] == esperado

    asiento = await test_db["economy_ledger"].find_one(
        {"_id": f"attempt:{user_id}:narrativo:{DATE}:normal"}
    )
    assert asiento["status"] == "applied"
