"""
testing_lab/frontend_endpoint_inventory.py
Escanea todo el frontend (src y admin_src) para inventariar todas las rutas HTTP llamadas
y cruzarlas contra las rutas que se propone eliminar del backend.
"""

import os
import re
import json

FRONTEND_DIR = os.path.abspath(os.path.abspath(r"c:\Users\nmonti\Desktop\proyectos\frontend"))

def find_endpoints_in_frontend():
    endpoint_pattern = re.compile(r'(/api/[a-zA-Z0-9_\-\/]+|/progreso/[a-zA-Z0-9_\-\/]+|/usuario[a-zA-Z0-9_\-\/]*)')
    
    findings = []
    
    for root, _, files in os.walk(FRONTEND_DIR):
        if any(ign in root for ign in ["node_modules", ".git", "dist", ".gemini"]):
            continue
        for file in files:
            if file.endswith((".ts", ".tsx", ".js", ".jsx")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, FRONTEND_DIR)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            # Evitar comentarios obvios
                            clean_line = line.strip()
                            if clean_line.startswith("//") or clean_line.startswith("/*") or clean_line.startswith("*"):
                                continue
                            matches = endpoint_pattern.findall(line)
                            for m in matches:
                                findings.append({
                                    "endpoint": m,
                                    "file": rel_path,
                                    "line": line_no,
                                    "code": clean_line[:120]
                                })
                except Exception:
                    pass
    return findings

def main():
    print("=== INVENTARIO DE RUTAS CONSUMIDAS POR EL FRONTEND ===")
    endpoints = find_endpoints_in_frontend()
    
    # Agrupar por endpoint
    by_endpoint = {}
    for item in endpoints:
        ep = item["endpoint"]
        # Normalizar si tiene query params o templates
        by_endpoint.setdefault(ep, []).append(item)

    print(f"Total de referencias encontradas: {len(endpoints)}")
    print(f"Rutas únicas detectadas: {len(by_endpoint)}\n")

    # Clasificar
    progreso_hits = {k: v for k, v in by_endpoint.items() if "progreso" in k}
    usuario_hits = {k: v for k, v in by_endpoint.items() if "usuario" in k}
    narrative_hits = {k: v for k, v in by_endpoint.items() if "narrative" in k}
    other_hits = {k: v for k, v in by_endpoint.items() if "progreso" not in k and "usuario" not in k and "narrative" not in k}

    print("1. Rutas de Progreso/Cursos:")
    if not progreso_hits:
        print("  -> CERO llamadas encontradas. Totalmente ausente del frontend.")
    else:
        for ep, hits in progreso_hits.items():
            print(f"  - {ep} ({len(hits)} llamadas)")

    print("\n2. Rutas de Usuario:")
    for ep, hits in usuario_hits.items():
        print(f"  - {ep} ({len(hits)} llamadas):")
        for h in hits:
            print(f"      [{h['file']}:{h['line']}] {h['code']}")

    print("\n3. Rutas Narrativas:")
    for ep, hits in sorted(narrative_hits.items()):
        print(f"  - {ep} ({len(hits)} llamadas)")

    # Guardar reporte
    out_file = os.path.join(os.path.dirname(__file__), "frontend_consumed_endpoints.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(by_endpoint, f, indent=2)

    print(f"\nReporte exportado a: {out_file}")

if __name__ == "__main__":
    main()
