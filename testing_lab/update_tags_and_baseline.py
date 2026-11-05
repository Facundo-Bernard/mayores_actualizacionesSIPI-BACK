"""
testing_lab/update_tags_and_baseline.py
1. Remueve 'Usuarios y Torre de Control' y 'Progreso de Cursos' de tags_metadata en app/main.py.
2. Remueve las violaciones resueltas de tests/unit/architecture_baseline.txt.
3. Regenera tests/contract/snapshots/openapi.json.
"""

import json
from pathlib import Path
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

def main():
    # 1. main.py
    main_path = os.path.join(BACKEND_DIR, "app", "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace('    {"name": "Usuarios y Torre de Control"},\n', '')
    content = content.replace('    {"name": "Progreso de Cursos"},\n', '')

    with open(main_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print("[OK] app/main.py tags_metadata actualizado.")

    # 2. architecture_baseline.txt
    baseline_path = os.path.join(BACKEND_DIR, "tests", "unit", "architecture_baseline.txt")
    with open(baseline_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = [l for l in lines if "app/features/usuario/" not in l]
    with open(baseline_path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)
    print("[OK] tests/unit/architecture_baseline.txt actualizado.")

    # 3. openapi snapshot
    from app.main import app
    spec = app.openapi()
    snapshot_path = Path(BACKEND_DIR) / "tests" / "contract" / "snapshots" / "openapi.json"
    snapshot_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] tests/contract/snapshots/openapi.json regenerado.")

if __name__ == "__main__":
    main()
