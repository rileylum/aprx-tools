import json
import sys
import zipfile
from pathlib import Path

from .util import aprx_for_src_dir
from . import connections as conn

_DOS_EPOCH = (1980, 1, 1, 0, 0, 0)


def _minify_json(data: bytes) -> bytes:
    parsed = json.loads(data.decode("utf-8"))
    return json.dumps(parsed, separators=(",", ":")).encode("utf-8")


def _minify_json_subst(data: bytes, key_to_value, fields, token, missing: set) -> bytes:
    parsed = json.loads(data.decode("utf-8"))
    parsed, miss = conn.substitute(parsed, key_to_value, fields, token)
    missing.update(miss)
    return json.dumps(parsed, separators=(",", ":")).encode("utf-8")


def pack(src_dir: str, output_path: str = None,
         env: str = None, connections_file: str = None) -> Path:
    """Pack an exploded .aprx.src directory back into an .aprx file.

    In an environment-managed project, @@tokens@@ in configured fields are
    substituted with the connection strings for the resolved environment (--env /
    --connections / default local.json).  Outside such a project it packs
    unchanged.  Returns the output file path.
    """
    src = Path(src_dir)
    if not src.is_dir():
        sys.exit(f"aprx-tools: {src} is not a directory")

    if output_path:
        out = Path(output_path)
    else:
        try:
            out = aprx_for_src_dir(src)
        except ValueError:
            out = src.parent / (src.name + ".aprx")

    # Resolve environment substitution (None -> simple mode, pack unchanged).
    project_dir = conn.find_project_config(src)
    conn_path = conn.resolve_connections_file(project_dir, env, connections_file)
    key_to_value = None
    if conn_path is not None:
        cfg = conn.load_config(project_dir)
        fields, token = cfg["fields"], cfg["token"]
        key_to_value = conn.load_connections(conn_path)
        print(f"  connections: {conn_path.name} ({len(key_to_value)} keys)")

    files = sorted(f for f in src.rglob("*") if f.is_file())

    # Build every entry first so a missing-key error fails before any output.
    entries = []  # (arcname, data: bytes)
    missing: set = set()
    for file in files:
        arcname = file.relative_to(src).as_posix()
        data = file.read_bytes()

        if file.suffix == ".json":
            try:
                if key_to_value is not None:
                    data = _minify_json_subst(data, key_to_value, fields, token, missing)
                else:
                    data = _minify_json(data)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  warning: could not minify {arcname}: {e}", file=sys.stderr)

        entries.append((arcname, data))

    if missing:
        sys.exit(
            f"aprx-tools: {conn_path.name} is missing connection keys: "
            + ", ".join(sorted(missing))
        )

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arcname, data in entries:
            info = zipfile.ZipInfo(arcname, date_time=_DOS_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)

    size_kb = out.stat().st_size // 1024
    print(f"  packed {src.name}/ → {out.name} ({size_kb} KB, {len(files)} files)")
    return out
