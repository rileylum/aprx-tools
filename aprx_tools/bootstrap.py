"""`aprx connections init` / `aprx connections check` — scaffold and validate the
per-environment connection files."""

import json
import re
import sys
import zipfile
from pathlib import Path

from . import connections as conn


def _suggest_key(value: str, taken: set) -> str:
    """Derive a short, stable key from a connection string.

    Prefers a .gdb / .sde basename, then a DATABASE=... value, falling back to
    conn1, conn2, ... — always disambiguated against keys already taken."""
    m = re.search(r"([^\\/=;]+)\.(?:gdb|sde)", value, re.IGNORECASE)
    if not m:
        m = re.search(r"DATABASE=([^;]+)", value, re.IGNORECASE)
    base = m.group(1) if m else ""
    base = re.sub(r"[^0-9a-zA-Z]+", "_", base.split("\\")[-1].split("/")[-1]).strip("_").lower()

    if not base:
        i = 1
        while f"conn{i}" in taken:
            i += 1
        return f"conn{i}"

    key, i = base, 2
    while key in taken:
        key, i = f"{base}_{i}", i + 1
    return key


def _scan_values(aprx: Path, fields) -> set:
    values: set = set()
    with zipfile.ZipFile(aprx) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            try:
                obj = json.loads(zf.read(name))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            values |= conn.collect_field_values(obj, fields)
    return values


def _write_json(path: Path, label: str, data: dict) -> bool:
    if path.exists():
        print(f"  exists, leaving as-is: {label}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {label}")
    return True


def connections_init(aprx_file: str) -> None:
    aprx = Path(aprx_file)
    if not aprx.exists():
        sys.exit(f"aprx-tools: {aprx} not found")

    project = conn.find_project_config(aprx.parent) or aprx.parent
    cfg = conn.load_config(conn.find_project_config(aprx.parent))
    fields, token = cfg["fields"], cfg["token"]

    values = _scan_values(aprx, fields)
    if not values:
        sys.exit(f"aprx-tools: no connection strings found in fields {fields} — "
                 f"nothing to scaffold")

    mapping: dict = {}
    for value in sorted(values):
        mapping[_suggest_key(value, set(mapping))] = value

    print(f"Found {len(mapping)} distinct connection string(s):")
    for key, value in mapping.items():
        print(f"  {key} = {value}")

    # aprx.json — project config (fields + token), written for discoverability
    _write_json(project / conn.CONFIG_FILENAME, conn.CONFIG_FILENAME,
                {"fields": fields, "token": token})
    # connections/dev.json — real values discovered from the .aprx
    _write_json(project / conn.CONNECTIONS_DIR / "dev.json",
                f"{conn.CONNECTIONS_DIR}/dev.json", mapping)
    # local.json.example — template a developer copies to local.json
    _write_json(project / "local.json.example", "local.json.example", mapping)

    print("\nNext steps:")
    print("  1. Add to .gitignore:")
    print("       local.json")
    print("       *.aprx")
    print("  2. cp local.json.example local.json   # then fill in your local paths")
    print("  3. Create connections/uat.json, connections/prd.json with the same keys.")
    print("  4. aprx explode <file>.aprx           # connection strings become @@tokens@@")


def connections_check() -> None:
    project = conn.find_project_config(Path.cwd())
    conn_dir = (project / conn.CONNECTIONS_DIR) if project else None
    if not conn_dir or not conn_dir.is_dir():
        sys.exit("aprx-tools: no connections/ directory found")

    files = sorted(conn_dir.glob("*.json"))
    if not files:
        sys.exit(f"aprx-tools: no connection files in {conn_dir}")

    maps = {f.name: conn.load_connections(f) for f in files}
    all_keys: set = set().union(*(set(m) for m in maps.values()))

    ok = True
    for name, m in maps.items():
        gaps = all_keys - set(m)
        if gaps:
            ok = False
            print(f"  {name}: missing {', '.join(sorted(gaps))}")

    if ok:
        print(f"OK — {len(files)} environment(s) define the same {len(all_keys)} key(s).")
    sys.exit(0 if ok else 1)
