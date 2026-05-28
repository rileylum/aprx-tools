import json
import sys
import zipfile
from pathlib import Path

from .util import aprx_for_src_dir

_DOS_EPOCH = (1980, 1, 1, 0, 0, 0)


def _minify_json(data: bytes) -> bytes:
    parsed = json.loads(data.decode("utf-8"))
    return json.dumps(parsed, separators=(",", ":")).encode("utf-8")


def pack(src_dir: str, output_path: str = None) -> Path:
    """Pack an exploded .aprx.src directory back into an .aprx file.

    Returns the output file path.
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

    files = sorted(f for f in src.rglob("*") if f.is_file())

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in files:
            arcname = file.relative_to(src).as_posix()
            data = file.read_bytes()

            if file.suffix == ".json":
                try:
                    data = _minify_json(data)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"  warning: could not minify {arcname}: {e}", file=sys.stderr)

            info = zipfile.ZipInfo(arcname, date_time=_DOS_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)

    size_kb = out.stat().st_size // 1024
    print(f"  packed {src.name}/ → {out.name} ({size_kb} KB, {len(files)} files)")
    return out
