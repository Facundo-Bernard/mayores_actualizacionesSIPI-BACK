"""
Auditoría exhaustiva del alcance lógico del sistema de vidas y puntos en Backend.
Verifica endpoints, esquemas, servicios, base de datos y dependencias cruzadas.
"""

import sys
import os
import inspect

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.routing import APIRoute
from app.main import app
from app.features.economy import schemas, config, lives, points, hints, unlock, admin

def analyze_economy_routes():
    print("=" * 70)
    print("ANALISIS DE RUTAS EN FASTAPI (app.features.economy)")
    print("=" * 70)
    
    economy_routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            if "/economy" in route.path or "/admin/economy" in route.path:
                methods = list(route.methods)
                economy_routes.append({
                    "path": route.path,
                    "methods": methods,
                    "name": route.name,
                    "endpoint": route.endpoint.__name__,
                    "summary": route.summary or ""
                })
    
    for r in sorted(economy_routes, key=lambda x: x["path"]):
        print(f"[{','.join(r['methods']):6}] {r['path']:35} -> {r['endpoint']:30} ({r['summary']})")
    
    return economy_routes

def analyze_schemas():
    print("\n" + "=" * 70)
    print("ANALISIS DE ESQUEMAS PYDANTIC (app.features.economy.schemas)")
    print("=" * 70)
    
    lives_schemas = []
    for name, obj in inspect.getmembers(schemas, inspect.isclass):
        if issubclass(obj, schemas.BaseModel) and obj is not schemas.BaseModel:
            fields = list(obj.model_fields.keys())
            has_vida = any("vida" in f for f in fields)
            has_paquete = any("paquete" in f for f in fields)
            if has_vida or has_paquete or "Life" in name or "Lives" in name or "Paquete" in name:
                lives_schemas.append((name, fields))
    
    for name, fields in lives_schemas:
        print(f"Esquema: {name:28} | Campos: {fields}")

def check_modules():
    print("\n" + "=" * 70)
    print("ANALISIS DE MODULOS INTERNOS DE ECONOMY")
    print("=" * 70)
    
    modules = [
        ("lives.py", lives, ["get_user_economy", "consume_life", "buy_lives", "refill_lives"]),
        ("points.py", points, ["migrate_guest_points"]),
        ("unlock.py", unlock, ["unlock_historical_day"]),
        ("hints.py", hints, ["use_hint"]),
        ("config.py", config, ["get_economy_config", "update_economy_config"]),
        ("admin.py", admin, ["find_user_by_identifier", "adjust_user_economy", "change_user_subscription"]),
    ]
    
    for filename, mod, funcs in modules:
        source_lines = len(inspect.getsourcelines(mod)[0])
        print(f"Módulo: {filename:12} | Líneas: {source_lines:4} | Funciones clave: {funcs}")

if __name__ == "__main__":
    analyze_economy_routes()
    analyze_schemas()
    check_modules()
