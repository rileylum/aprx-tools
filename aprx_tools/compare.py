import difflib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def _load(path: Path) -> dict:
    if path.is_dir():
        return {
            f.relative_to(path).as_posix(): f.read_bytes()
            for f in path.rglob("*")
            if f.is_file()
        }
    with zipfile.ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _normalise_json(data: bytes) -> str:
    return json.dumps(json.loads(data.decode("utf-8")), indent=2, ensure_ascii=False) + "\n"


def _normalise_xml(data: bytes) -> str:
    def _strip(elem):
        if elem.text and not elem.text.strip():
            elem.text = None
        if elem.tail and not elem.tail.strip():
            elem.tail = None
        for child in elem:
            _strip(child)

    root = ET.fromstring(data.decode("utf-8"))
    _strip(root)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _normalise(name: str, data: bytes) -> str:
    if name.endswith(".json"):
        return _normalise_json(data)
    if name.endswith(".xml"):
        return _normalise_xml(data)
    return data.decode("utf-8", errors="replace")


def compare(path_a: str, path_b: str) -> bool:
    """Compare two .aprx files or directories semantically.

    Returns True if any differences were found.
    """
    pa, pb = Path(path_a), Path(path_b)
    files_a, files_b = _load(pa), _load(pb)
    names_a, names_b = set(files_a), set(files_b)

    diffs_found = False

    for name in sorted(names_a - names_b):
        print(f"only in {pa.name}: {name}")
        diffs_found = True
    for name in sorted(names_b - names_a):
        print(f"only in {pb.name}: {name}")
        diffs_found = True

    for name in sorted(names_a & names_b):
        try:
            text_a = _normalise(name, files_a[name])
            text_b = _normalise(name, files_b[name])
        except Exception as e:
            print(f"  could not parse {name}: {e}")
            diffs_found = True
            continue

        if text_a == text_b:
            continue

        diffs_found = True
        lines = list(difflib.unified_diff(
            text_a.splitlines(),
            text_b.splitlines(),
            fromfile=f"{pa.name}/{name}",
            tofile=f"{pb.name}/{name}",
            lineterm="",
            n=3,
        ))
        print("\n".join(lines))

    return diffs_found
