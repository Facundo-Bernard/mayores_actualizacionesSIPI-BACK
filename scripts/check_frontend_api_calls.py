"""Compara las llamadas /api/ del frontend con las rutas que expone el backend.

Uso:
    python scripts/check_frontend_api_calls.py
    python scripts/check_frontend_api_calls.py --strict

`--strict` sale con código 1 si encuentra una llamada que no matchea ninguna ruta
del backend, salvo las que se construyen por concatenación (se marcan como dinámicas).
"""

import argparse
import os
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = Path(os.environ.get("FRONTEND_DIR", BACKEND_ROOT.parent.parent / "frontend"))
SCAN_DIRS = ("src", "admin_src")
FILE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}
CALL_PATTERN = re.compile(r"""["'`](/api/[^"'`\s]*)""")
ROUTE_PARAM = re.compile(r"\{[^}]+\}")


def extract_calls(frontend_root: Path):
    calls = []
    for subdir in SCAN_DIRS:
        base = frontend_root / subdir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in FILE_EXTENSIONS or not path.is_file():
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for match in CALL_PATTERN.finditer(line):
                    raw = match.group(1)
                    path_only = raw.split("?", 1)[0].rstrip("/") or "/"
                    calls.append((path_only, raw, path.relative_to(frontend_root), line_number))
    return calls


def backend_routes():
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.main import app

    return list(app.openapi().get("paths", {}))


def matches(call_path: str, route: str) -> bool:
    route_pattern = ROUTE_PARAM.sub(r"[^/]+", route).rstrip("/") or "/"
    return re.fullmatch(route_pattern, call_path) is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    routes = backend_routes()
    calls = extract_calls(FRONTEND_ROOT)

    unmatched = []
    for call_path, raw, file_path, line_number in calls:
        if any(matches(call_path, route) for route in routes):
            continue
        is_dynamic = "${" in raw or call_path.endswith("/")
        unmatched.append((call_path, file_path, line_number, is_dynamic))

    print(f"Frontend: {FRONTEND_ROOT}")
    print(f"Llamadas /api/: {len(calls)} | rutas backend: {len(routes)}")
    print(f"Sin ruta backend: {len(unmatched)}")
    for call_path, file_path, line_number, is_dynamic in sorted(unmatched):
        suffix = " (dinámica)" if is_dynamic else ""
        print(f"  {call_path}  ->  {file_path}:{line_number}{suffix}")

    if args.strict and any(not item[3] for item in unmatched):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
