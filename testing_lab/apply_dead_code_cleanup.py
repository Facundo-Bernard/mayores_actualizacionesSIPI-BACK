"""
testing_lab/apply_dead_code_cleanup.py
Aplica las modificaciones quirÃºrgicas para extirpar:
- Cursos (app/features/progreso/)
- Estados y Alumnos (app/features/usuario/)
- Dependencias asociadas en app/main.py, app/core/database.py, app/core/dependencies.py, app/features/auth/service.py, app/scripts/init_db.py
- Purga en MongoDB (drop de estados_usuario y $unset en usuarios)
"""

import os
import shutil
import asyncio
from pymongo import MongoClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(BACKEND_DIR, "app")

def update_main_py():
    path = os.path.join(APP_DIR, "main.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    for line in lines:
        if "seed_estados_usuario" in line and "import" in line:
            continue
        if "usuario_router" in line and "import" in line:
            continue
        if "progreso_router" in line and "import" in line:
            continue
        if "try:" in line and "await seed_estados_usuario()" in (new_lines[-1] if new_lines else ""):
            continue
        if "await seed_estados_usuario()" in line:
            # quitar tambiÃ©n el try previo si estÃ¡
            if new_lines and "try:" in new_lines[-1]:
                new_lines.pop()
            skip = True
            continue
        if skip:
            if "logger.warning" in line and "estados de usuario" in line:
                skip = False
                continue
            if not line.strip() or line.strip().startswith("import"):
                skip = False
            else:
                continue

        if "app.include_router(usuario_router)" in line:
            continue
        if "app.include_router(progreso_router)" in line:
            continue
        if "# InclusiÃ³n de routers esenciales (Auth, Usuarios, Progreso de Cursos, DesafÃ­os, Narrativo, SSO)" in line:
            line = "# InclusiÃ³n de routers esenciales (Auth, DesafÃ­os, Narrativo, EconomÃ­a, SSO)\n"

        new_lines.append(line)

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("âœ“ app/main.py actualizado.")

def update_database_py():
    path = os.path.join(APP_DIR, "core", "database.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    for line in lines:
        if "# Ãndices de Estados de Usuario (estados_usuario)" in line:
            skip = True
            continue
        if skip:
            if "estados_usuario" in line or "await estados_usuario" in line:
                continue
            else:
                skip = False

        new_lines.append(line)

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("âœ“ app/core/database.py actualizado.")

def update_dependencies_py():
    path = os.path.join(APP_DIR, "core", "dependencies.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if '"estado_id": 2,' in line or '"estado_codigo": "ACTIVO",' in line:
            continue
        if '"progresos": []' in line:
            continue
        new_lines.append(line)

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("âœ“ app/core/dependencies.py actualizado.")

def update_auth_service_py():
    path = os.path.join(APP_DIR, "features", "auth", "service.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if '"progresos": [],' in line:
            continue
        new_lines.append(line)

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("âœ“ app/features/auth/service.py actualizado.")

def remove_feature_folders():
    progreso_dir = os.path.join(APP_DIR, "features", "progreso")
    if os.path.exists(progreso_dir):
        shutil.rmtree(progreso_dir)
        print("âœ“ Eliminado directorio: app/features/progreso")

    usuario_dir = os.path.join(APP_DIR, "features", "usuario")
    if os.path.exists(usuario_dir):
        shutil.rmtree(usuario_dir)
        print("âœ“ Eliminado directorio: app/features/usuario")

    init_db_file = os.path.join(APP_DIR, "scripts", "init_db.py")
    if os.path.exists(init_db_file):
        os.remove(init_db_file)
        print("âœ“ Eliminado archivo: app/scripts/init_db.py")

def cleanup_mongodb():
    client = MongoClient("mongodb://localhost:27017")
    db = client["mayores_actualizaciones_dev"]
    
    # 1. Drop estados_usuario
    colls = db.list_collection_names()
    if "estados_usuario" in colls:
        db["estados_usuario"].drop()
        print("âœ“ MongoDB: ColecciÃ³n 'estados_usuario' eliminada (drop).")

    # 2. $unset campos en usuarios
    res = db["usuarios"].update_many(
        {},
        {"$unset": {
            "progresos": "",
            "date_start": "",
            "date_end": "",
            "estado_id": "",
            "estado_codigo": "",
            "black": ""
        }}
    )
    print(f"âœ“ MongoDB: ColecciÃ³n 'usuarios' depurada ({res.modified_count} documentos actualizados con $unset).")

def main():
    print("=== APLICANDO LIMPIEZA DE CÃ“DIGO MUERTO ===")
    update_main_py()
    update_database_py()
    update_dependencies_py()
    update_auth_service_py()
    remove_feature_folders()
    cleanup_mongodb()
    print("\nÂ¡Limpieza completada exitosamente!")

if __name__ == "__main__":
    main()

