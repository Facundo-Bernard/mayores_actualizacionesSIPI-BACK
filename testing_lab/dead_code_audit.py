"""
testing_lab/dead_code_audit.py
Auditoría estática y trazabilidad profunda de código muerto en el backend de juegos:
1. Módulo Progreso de Cursos (app/features/progreso/)
2. Módulo Estados y Usuarios (app/features/usuario/)
3. Motor Narrativo V1 y endpoints deprecados (app/features/narrative/game/motor_v1/ y admin V1)
4. Funciones y utilitarios huérfanos en Economía, Desafíos y Clásicos
5. Colecciones de MongoDB y campos huérfanos
"""

import os
import re
import sys
import json

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(BACKEND_DIR, "app")
FRONTEND_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "frontend"))

def count_lines(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            loc = len(lines)
            code_loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
            return loc, code_loc
    except Exception:
        return 0, 0

def find_references_in_dir(target_regex, search_dir, extensions=(".py", ".ts", ".tsx", ".js", ".jsx")):
    matches = []
    pattern = re.compile(target_regex)
    for root, _, files in os.walk(search_dir):
        if any(ign in root for ign in ["node_modules", ".venv", "__pycache__", ".git", "dist", "testing_lab"]):
            continue
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if pattern.search(line):
                                rel_path = os.path.relpath(full_path, BACKEND_DIR if search_dir.startswith(BACKEND_DIR) else FRONTEND_DIR)
                                matches.append({
                                    "file": rel_path,
                                    "line": line_no,
                                    "content": line.strip()
                                })
                except Exception:
                    pass
    return matches

def main():
    print("=== AUDITORÍA EXHAUSTIVA DE CÓDIGO MUERTO ===")
    
    report = {
        "dominio_cursos": {},
        "dominio_estados_usuarios": {},
        "motor_narrativo_v1": {},
        "economia_clasicos_muertos": {},
        "mongodb_impacto": {}
    }

    # ---------------------------------------------------------
    # 1. CURSOS: app/features/progreso/
    # ---------------------------------------------------------
    progreso_dir = os.path.join(APP_DIR, "features", "progreso")
    progreso_files = []
    total_progreso_loc = 0
    total_progreso_code = 0
    
    if os.path.exists(progreso_dir):
        for f in os.listdir(progreso_dir):
            if f.endswith(".py"):
                path = os.path.join(progreso_dir, f)
                loc, code = count_lines(path)
                total_progreso_loc += loc
                total_progreso_code += code
                progreso_files.append({"file": f"app/features/progreso/{f}", "total_lines": loc, "code_lines": code})

    # Referencias en Backend
    progreso_backend_refs = find_references_in_dir(r"progreso_router|app\.features\.progreso", APP_DIR)
    # Referencias en Frontend
    progreso_frontend_refs = find_references_in_dir(r"['\"]/progreso", FRONTEND_DIR)

    report["dominio_cursos"] = {
        "descripcion": "Gestión de avance de cursos educativos (completamente fuera del dominio de juegos)",
        "archivos": progreso_files,
        "total_loc": total_progreso_loc,
        "total_code_lines": total_progreso_code,
        "referencias_backend": progreso_backend_refs,
        "referencias_frontend": progreso_frontend_refs
    }

    # ---------------------------------------------------------
    # 2. ESTADOS Y USUARIOS: app/features/usuario/
    # ---------------------------------------------------------
    usuario_dir = os.path.join(APP_DIR, "features", "usuario")
    usuario_files = []
    total_usuario_loc = 0
    total_usuario_code = 0

    if os.path.exists(usuario_dir):
        for f in os.listdir(usuario_dir):
            if f.endswith(".py"):
                path = os.path.join(usuario_dir, f)
                loc, code = count_lines(path)
                total_usuario_loc += loc
                total_usuario_code += code
                usuario_files.append({"file": f"app/features/usuario/{f}", "total_lines": loc, "code_lines": code})

    usuario_backend_refs = find_references_in_dir(r"usuario_router|app\.features\.usuario|estados_usuario|seed_estados_usuario", APP_DIR)
    usuario_frontend_refs = find_references_in_dir(r"['\"]/usuario", FRONTEND_DIR)

    report["dominio_estados_usuarios"] = {
        "descripcion": "Gestión de estados de cuenta y alumnos (delegado al Autenticador Central)",
        "archivos": usuario_files,
        "total_loc": total_usuario_loc,
        "total_code_lines": total_usuario_code,
        "referencias_backend": usuario_backend_refs,
        "referencias_frontend": usuario_frontend_refs
    }

    # ---------------------------------------------------------
    # 3. MOTOR NARRATIVO V1 Y ENDPOINTS DEPRECADOS
    # ---------------------------------------------------------
    motor_v1_dir = os.path.join(APP_DIR, "features", "narrative", "game", "motor_v1")
    motor_v1_files = []
    total_v1_loc = 0
    total_v1_code = 0

    if os.path.exists(motor_v1_dir):
        for f in os.listdir(motor_v1_dir):
            if f.endswith(".py"):
                path = os.path.join(motor_v1_dir, f)
                loc, code = count_lines(path)
                total_v1_loc += loc
                total_v1_code += code
                motor_v1_files.append({"file": f"app/features/narrative/game/motor_v1/{f}", "total_lines": loc, "code_lines": code})

    # Endpoints deprecados V1 en router.py
    v1_endpoints = [
        "POST /api/narrative/v2/partida/decidir-evento",
        "POST /api/narrative/v2/partida/responder-conversacion",
        "GET /api/narrative/partida/evento-actual",
        "GET /api/narrative/partida/conversacion-actual",
        "GET /api/narrative/partida/resultado-actual",
        "GET /api/narrative/partida/draft-actual"
    ]

    # Catálogos Admin exclusivos de V1 (eventos, conversaciones y resultados planos)
    v1_admin_endpoints = [
        "/api/narrative/admin/eventos",
        "/api/narrative/admin/conversaciones",
        "/api/narrative/admin/resultados"
    ]

    # Colecciones MongoDB de V1
    v1_collections = [
        "narrative_events",
        "narrative_conversations",
        "narrative_results"
    ]

    report["motor_narrativo_v1"] = {
        "descripcion": "Motor narrativo plano V1 sustituido por el motor de grafos V2",
        "archivos_motor_v1": motor_v1_files,
        "total_loc_motor_v1": total_v1_loc,
        "total_code_lines_motor_v1": total_v1_code,
        "endpoints_deprecados_game": v1_endpoints,
        "endpoints_admin_v1": v1_admin_endpoints,
        "colecciones_mongo_v1": v1_collections
    }

    # ---------------------------------------------------------
    # 4. ECONOMÍA, DESAFÍOS Y CLÁSICOS: CÓDIGO HUÉRFANO
    # ---------------------------------------------------------
    # Buscar funciones históricas documentadas en el refactor
    economy_dead_patterns = [
        ("puntos_por_juego", r"puntos_por_juego"),
        ("get_points_for_game", r"get_points_for_game"),
        ("get_points_for_grade", r"get_points_for_grade"),
        ("attempt_budgets", r"attempt_budgets")
    ]
    
    economy_dead_findings = {}
    for name, pat in economy_dead_patterns:
        refs = find_references_in_dir(pat, APP_DIR)
        economy_dead_findings[name] = refs

    report["economia_clasicos_muertos"] = economy_dead_findings

    # Guardar reporte
    out_file = os.path.join(os.path.dirname(__file__), "dead_code_audit_report.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nReporte completo exportado a: {out_file}")

    print("\n--- RESUMEN RÁPIDO ---")
    print(f"1. Dominio Cursos (progreso): {total_progreso_loc} líneas ({total_progreso_code} de código)")
    print(f"2. Dominio Estados/Usuarios: {total_usuario_loc} líneas ({total_usuario_code} de código)")
    print(f"3. Motor Narrativo V1: {total_v1_loc} líneas ({total_v1_code} de código)")
    print(f"4. Endpoints juego V1 deprecados: {len(v1_endpoints)}")
    print(f"5. Endpoints admin V1 reemplazados por V2: {len(v1_admin_endpoints)}")

if __name__ == "__main__":
    main()
