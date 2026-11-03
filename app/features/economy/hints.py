"""Pistas: resolución idempotente y cobro posterior a la entrega."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.features.economy.config import get_economy_config
from app.features.economy.schemas import UseHintResponse
from app.shared.clock import today_str

logger = logging.getLogger("EconomyService")

COLL_HINTS = "user_hints"


async def _find_hint_challenge(db: Any, game_id: str, target_date: str, difficulty: str) -> Optional[dict]:
    challenge = await db["daily_challenges"].find_one(
        {"game_id": game_id, "date": target_date, "difficulty": difficulty}
    )
    if challenge:
        return challenge
    candidates = await db["daily_challenges"].find(
        {"game_id": game_id, "date": target_date}
    ).limit(2).to_list(length=2)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _resolve_hint(config: dict, game: str, req: Any) -> Tuple[Optional[str], Any, str]:
    """Devuelve (texto, valor_revelado, hint_key) sin cobrar nada."""
    pista_texto = None
    valor_revelado = None
    idx = req.hint_index or 0
    hint_key = f"hint:{idx}"

    if game == "wordle":
        hints = config.get("hints") or []
        if hints:
            idx = idx if 0 <= idx < len(hints) else 0
            pista_texto = hints[idx]
            hint_key = f"hint:{idx}"
        elif config.get("solution"):
            pista_texto = f"Empieza con la letra '{config['solution'][0]}'"
            hint_key = "letter:first"

    elif game == "sudoku":
        sol = config.get("solution")
        if (
            sol
            and req.row is not None
            and req.col is not None
            and 0 <= req.row < 9
            and 0 <= req.col < 9
        ):
            valor_revelado = sol[req.row][req.col]
            pista_texto = (
                f"El número en la fila {req.row + 1}, "
                f"columna {req.col + 1} es {valor_revelado}"
            )
            hint_key = f"cell:{req.row}:{req.col}"

    elif game == "sopa_letras":
        hints = config.get("hints") or []
        words = config.get("words") or []
        if hints and 0 <= idx < len(hints):
            pista_texto = hints[idx]
        elif words and 0 <= idx < len(words):
            pista_texto = f"Palabra a buscar: {words[idx]}"
            hint_key = f"word:{idx}"

    elif game == "crucigrama":
        words = config.get("words") or []
        if req.row is not None and req.col is not None:
            hint_key = f"cell:{req.row}:{req.col}"
            for w in words:
                coords = w.get("coords") or []
                word_str = w.get("word", "")
                for i, coord in enumerate(coords):
                    if len(coord) < 2:
                        continue
                    r, cl = coord[0], coord[1]
                    if r == req.row and cl == req.col and i < len(word_str):
                        valor_revelado = word_str[i]
                        pista_texto = (
                            f"La letra en ({req.row + 1}, {req.col + 1}) "
                            f"es '{valor_revelado}'"
                        )
                        break
                if valor_revelado is not None:
                    break
        elif words and 0 <= idx < len(words):
            pista_texto = (
                f"{words[idx].get('direction', 'Horiz.')} "
                f"{words[idx].get('number', '')}: {words[idx].get('clue', '')}"
            )
            hint_key = f"word:{idx}"

    return (pista_texto, valor_revelado, hint_key)


async def _hint_response_from_record(record: dict, user: dict, costo: int, replayed: bool) -> UseHintResponse:
    puntos_actuales = int(user.get("puntos", 0))
    return UseHintResponse(
        success=True,
        puntos_restantes=puntos_actuales,
        puntos_descontados=0,
        vidas_restantes=int(user.get("vidas") or 5),
        vidas_descontadas=0,
        pista=record.get("pista"),
        valor_revelado=record.get("valor_revelado"),
        message=(
            "Esta pista ya fue desbloqueada; no se descontaron puntos."
            if replayed
            else f"Pista desbloqueada exitosamente (-{costo} puntos)."
        ),
    )


async def use_hint(user_id: int, req: Any) -> UseHintResponse:
    """
    Entrega una pista y descuenta puntos solo si hay contenido y no se entregó antes.
    """
    db = get_database()
    config = await get_economy_config()
    costo = int(config.costo_pista_puntos or 20)

    game = req.game_id.lower().strip()
    target_date = req.date or today_str()
    difficulty = (req.difficulty or "").strip().lower() or None
    if not difficulty:
        attempt = await db["user_attempts"].find_one(
            {"user_id": user_id, "game_id": game, "date": target_date}
        )
        difficulty = str((attempt or {}).get("difficulty") or "standard").lower()
    difficulty = difficulty or "standard"

    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} no encontrado.",
        )

    challenge = await _find_hint_challenge(db, game, target_date, difficulty)
    pista_texto = None
    valor_revelado = None
    hint_key = f"hint:{req.hint_index or 0}"
    if challenge and "config" in challenge:
        try:
            pista_texto, valor_revelado, hint_key = _resolve_hint(
                challenge["config"] or {}, game, req
            )
        except Exception as e:
            logger.warning(f"[ECONOMIA] No se pudo resolver la pista de {game}: {e}")

    if pista_texto is None and valor_revelado is None:
        return UseHintResponse(
            success=True,
            puntos_restantes=int(user.get("puntos", 0)),
            puntos_descontados=0,
            vidas_restantes=int(user.get("vidas") or 5),
            vidas_descontadas=0,
            pista=None,
            valor_revelado=None,
            message="No hay pista disponible para este desafío; no se descontaron puntos.",
        )

    hint_filter = {
        "user_id": user_id,
        "game_id": game,
        "date": target_date,
        "difficulty": difficulty,
        "hint_key": hint_key,
    }
    existing = await db[COLL_HINTS].find_one(hint_filter)
    if existing:
        return await _hint_response_from_record(existing, user, costo, replayed=True)

    now = datetime.now(timezone.utc)
    record = {
        **hint_filter,
        "pista": pista_texto,
        "valor_revelado": valor_revelado,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db[COLL_HINTS].insert_one(record)
    except DuplicateKeyError:
        existing = await db[COLL_HINTS].find_one(hint_filter)
        if existing:
            return await _hint_response_from_record(existing, user, costo, replayed=True)
        raise

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": costo}},
        {
            "$inc": {"puntos": -costo},
            "$set": {"updated_at": now},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        await db[COLL_HINTS].delete_one({"_id": record["_id"]})
        user_actual = await db["usuarios"].find_one({"id": user_id})
        puntos_actuales = int(user_actual.get("puntos", 0)) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Puntos insuficientes para pedir una pista. Cuesta {costo} pts "
                f"y tenés {puntos_actuales} pts."
            ),
        )

    nuevos_puntos = int(result.get("puntos", 0))
    await db[COLL_HINTS].update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "status": "applied",
                "puntos_descontados": costo,
                "saldo_despues": nuevos_puntos,
                "updated_at": now,
            }
        },
    )
    logger.info(
        f"[ECONOMIA] Usuario {user_id} consumió {costo} pts por pista en "
        f"{game}/{difficulty}/{target_date}. Restan: {nuevos_puntos} pts"
    )

    return UseHintResponse(
        success=True,
        puntos_restantes=nuevos_puntos,
        puntos_descontados=costo,
        vidas_restantes=int(result.get("vidas") or 5),
        vidas_descontadas=0,
        pista=pista_texto,
        valor_revelado=valor_revelado,
        message=f"Pista desbloqueada exitosamente (-{costo} puntos)."
    )
