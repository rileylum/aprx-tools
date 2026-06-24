import json
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .util import src_dir_for
from .transform import IDENTITY


def _format_xml(data: bytes) -> str:
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    ET.register_namespace("xs", "http://www.w3.org/2001/XMLSchema")
    ET.register_namespace("typens", "http://www.esri.com/schemas/ArcGIS/3.6.0")
    root = ET.fromstring(data.decode("utf-8"))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def explode(aprx_path: str, output_dir: str = None, transform=IDENTITY) -> Path:
    """Extract an .aprx into a version-controllable directory.

    The version-control core knows nothing about connections (ADR-0002): it parses
    each JSON entry, hands it to ``transform.apply`` (which may rewrite it in place),
    and pretty-prints the result. Simple mode passes the no-op ``IDENTITY``;
    environment mode passes a ``Substitution`` that tokenises connection strings. The
    composition root (CLI / hooks) chooses which, so a direct ``aprx explode`` of an
    environment-mode project still produces neutral source.

    The transform is two-phase: ``apply`` runs per entry, then ``raise_if_problems``
    fires once after every entry is computed but **before** anything is written — so a
    bad entry (e.g. an unregistered connection string) aborts the whole operation
    without deleting or overwriting the existing src directory. Returns the output dir.
    """
    aprx = Path(aprx_path)
    if not aprx.exists():
        sys.exit(f"aprx-tools: {aprx} not found")

    out = Path(output_dir) if output_dir else src_dir_for(aprx)

    # Compute every entry first so a transform problem fails before we delete or
    # overwrite the existing src directory.
    payloads = []  # (name, data: str | bytes)
    with zipfile.ZipFile(aprx, "r") as zf:
        for name in sorted(zf.namelist()):
            raw = zf.read(name)
            payload = raw

            if name.endswith(".json"):
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                    transform.apply(parsed)
                    payload = json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
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

    # Phase 2: surface every accumulated problem at once, before touching the filesystem.
    transform.raise_if_problems()

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
