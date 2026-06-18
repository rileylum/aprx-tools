import json
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .util import src_dir_for
from . import connections as conn


def _format_json(data: bytes) -> str:
    parsed = json.loads(data.decode("utf-8"))
    return json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"


def _format_json_tokenize(data: bytes, value_to_key, fields, token, unknown: set) -> str:
    parsed = json.loads(data.decode("utf-8"))
    parsed, unk = conn.tokenize(parsed, value_to_key, fields, token)
    unknown.update(unk)
    return json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"


def _format_xml(data: bytes) -> str:
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    ET.register_namespace("xs", "http://www.w3.org/2001/XMLSchema")
    ET.register_namespace("typens", "http://www.esri.com/schemas/ArcGIS/3.6.0")
    root = ET.fromstring(data.decode("utf-8"))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def explode(aprx_path: str, output_dir: str = None) -> Path:
    """Extract an .aprx into a version-controllable directory.

    In an environment-managed project, connection strings in configured fields are
    replaced with @@tokens@@ so the committed source is environment-neutral.
    Returns the output directory path.
    """
    aprx = Path(aprx_path)
    if not aprx.exists():
        sys.exit(f"aprx-tools: {aprx} not found")

    out = Path(output_dir) if output_dir else src_dir_for(aprx)

    # Environment tokenisation (None -> simple mode, raw strings kept verbatim).
    project_dir = conn.find_project_config(aprx.parent)
    value_to_key = fields = token = None
    if project_dir is not None:
        files = conn.connection_files(project_dir)
        if files:
            value_to_key = conn.build_reverse_map(files)
            cfg = conn.load_config(project_dir)
            fields, token = cfg["fields"], cfg["token"]

    # Compute every entry first so an unregistered connection string fails before
    # we delete or overwrite the existing src directory.
    payloads = []  # (name, data: str | bytes)
    unknown: set = set()
    with zipfile.ZipFile(aprx, "r") as zf:
        for name in sorted(zf.namelist()):
            raw = zf.read(name)
            payload = raw

            if name.endswith(".json"):
                try:
                    if value_to_key is not None:
                        payload = _format_json_tokenize(raw, value_to_key, fields, token, unknown)
                    else:
                        payload = _format_json(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"  warning: could not parse JSON in {name}: {e}", file=sys.stderr)
                    payload = raw

            elif name.endswith(".xml"):
                try:
                    payload = _format_xml(raw)
                except Exception as e:
                    print(f"  warning: could not parse XML in {name}: {e}", file=sys.stderr)
                    payload = raw

            payloads.append((name, payload))

    if unknown:
        sys.exit(
            "aprx-tools: unregistered connection string(s) — add them to your "
            "connection files before committing:\n  " + "\n  ".join(sorted(unknown))
        )

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name, payload in payloads:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            target.write_text(payload, encoding="utf-8")
        else:
            target.write_bytes(payload)

    file_count = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"  exploded {aprx.name} → {out.name}/ ({file_count} files)")
    return out
