import asyncio
import logging
import mysql.connector
from datetime import datetime, date
import os
from app.core.database import get_database, connect_to_mongo, close_mongo_connection, set_sequence_value

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MigrateETL")

async def run_migration():
    logger.info("=== INICIANDO MIGRACIÓN DE MYSQL A MONGODB ===")
    
    # 1. Conexión a MySQL
    logger.info(f"Conectando a MySQL en {os.getenv("MYSQL_HOST", "localhost")}:{int(os.getenv("MYSQL_PORT", 3306))}/{os.getenv("MYSQL_DATABASE", "prueba2")}...")
    try:
        mysql_conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "root"),
            database=os.getenv("MYSQL_DATABASE", "prueba2")
        )
        cursor = mysql_conn.cursor(dictionary=True)
        logger.info("Conexión a MySQL exitosa.")
    except Exception as e:
        logger.error(f"Error conectando a MySQL: {e}")
        return

    # 2. Conectar a MongoDB
    await connect_to_mongo()
    db = get_database()

    # 3. Extraer usuarios de MySQL
    logger.info("Extrayendo usuarios de MySQL...")
    cursor.execute("""
        SELECT id, name, email, password, tipo_usuario, is_black, activo, codigo_acceso, date_start, date_end 
        FROM usuario
    """)
    usuarios_mysql = cursor.fetchall()
    logger.info(f"Se encontraron {len(usuarios_mysql)} usuarios en MySQL.")

    # 4. Extraer progresos de MySQL
    logger.info("Extrayendo progresos de MySQL...")
    cursor.execute("""
        SELECT id, progreso, completado, examen_puntos, curso_id, usuario_id 
        FROM progreso_usuario
    """)
    progresos_mysql = cursor.fetchall()
    logger.info(f"Se encontraron {len(progresos_mysql)} registros de progreso en MySQL.")

    # Agrupar progresos por usuario_id
    progresos_por_usuario = {}
    max_progreso_id = 0
    for p in progresos_mysql:
        u_id = p["usuario_id"]
        prog_id = p["id"]
        if prog_id > max_progreso_id:
            max_progreso_id = prog_id

        item = {
            "id": prog_id,
            "cursoId": p["curso_id"],
            "usuarioId": u_id,
            "progreso": p["progreso"],
            "completado": bool(p["completado"]),
            "examenPuntos": p["examen_puntos"],
            "updatedAt": datetime.now()
        }
        progresos_por_usuario.setdefault(u_id, []).append(item)

    # 5. Insertar en MongoDB
    max_user_id = 0
    migrados_count = 0

    for u in usuarios_mysql:
        user_id = u["id"]
        if user_id > max_user_id:
            max_user_id = user_id

        d_start = u["date_start"]
        if isinstance(d_start, datetime):
            pass
        elif isinstance(d_start, date):
            d_start = datetime.combine(d_start, datetime.min.time())
        elif not d_start:
            d_start = datetime.now()

        d_end = u["date_end"].strftime("%Y-%m-%d") if isinstance(u["date_end"], (date, datetime)) else u["date_end"]

        doc = {
            "id": user_id,
            "name": u["name"] or "",
            "email": (u["email"] or "").lower().strip(),
            "password": u["password"], # Hash BCrypt preservado
            "codigo_acceso": u["codigo_acceso"],
            "tipo_usuario": u["tipo_usuario"] if u["tipo_usuario"] is not None else 1,
            "black": bool(u["is_black"]),
            "activo": bool(u["activo"]) if u["activo"] is not None else True,
            "date_start": d_start,
            "date_end": d_end,
            "progresos": progresos_por_usuario.get(user_id, [])
        }

        # Upsert por email para no duplicar si se corre más de una vez
        await db["usuarios"].update_one(
            {"id": user_id},
            {"$set": doc},
            upsert=True
        )
        migrados_count += 1

    # 6. Actualizar las secuencias atómicas en counters
    if max_user_id > 0:
        await set_sequence_value("usuario_id", max_user_id)
        logger.info(f"Secuencia 'usuario_id' configurada en {max_user_id}.")

    if max_progreso_id > 0:
        await set_sequence_value("progreso_id", max_progreso_id)
        logger.info(f"Secuencia 'progreso_id' configurada en {max_progreso_id}.")

    cursor.close()
    mysql_conn.close()
    await close_mongo_connection()

    logger.info(f"=== MIGRACIÓN FINALIZADA CON ÉXITO: {migrados_count} usuarios migrados ===")

if __name__ == "__main__":
    asyncio.run(run_migration())
