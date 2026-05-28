import json
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .util import src_dir_for


def _format_json(data: bytes) -> str:
    parsed = json.loads(data.decode("utf-8"))
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

    Returns the output directory path.
    """
    aprx = Path(aprx_path)
    if not aprx.exists():
        sys.exit(f"aprx-tools: {aprx} not found")

    out = Path(output_dir) if output_dir else src_dir_for(aprx)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    with zipfile.ZipFile(aprx, "r") as zf:
        for name in sorted(zf.namelist()):
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = zf.read(name)

            if name.endswith(".json"):
                try:
                    target.write_text(_format_json(raw), encoding="utf-8")
                    continue
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"  warning: could not parse JSON in {name}: {e}", file=sys.stderr)

            elif name.endswith(".xml"):
                try:
                    target.write_text(_format_xml(raw), encoding="utf-8")
                    continue
                except Exception as e:
                    print(f"  warning: could not parse XML in {name}: {e}", file=sys.stderr)

            target.write_bytes(raw)

    file_count = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"  exploded {aprx.name} → {out.name}/ ({file_count} files)")
    return out
