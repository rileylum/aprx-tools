#!/usr/bin/env bash
# Creates a self-contained git repo at ~/aprx-demo with two diverging feature branches
# that produce a merge conflict in readable JSON.
# Run this once before recording the VHS demo.
set -euo pipefail

DEMO_DIR="${1:-$HOME/aprx-demo}"

echo "Creating demo repo at $DEMO_DIR..."
rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR"
cd "$DEMO_DIR"

git init -q
git config user.email "gis@example.com"
git config user.name "GIS Dev"

# Mark .aprx as binary so git never tries to text-merge it
echo "*.aprx binary" > .gitattributes

# ── Initial project files ──────────────────────────────────────────────────────

mkdir -p map.aprx.src/map

cat > map.aprx.src/GISProject.json << 'EOF'
{
  "type": "CIMMapDocument",
  "version": "3.0.0",
  "title": "Acme Site Analysis",
  "defaultCamera": { "scale": 50000 },
  "layers": [
    "CIMPATH=map/roads.json",
    "CIMPATH=map/parcels.json"
  ]
}
EOF

cat > map.aprx.src/DocumentInfo.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<DocumentInfo>
  <Title>Acme Site Analysis</Title>
  <Subject>Site analysis layers for Acme projects</Subject>
  <Author>Acme Geospatial</Author>
  <Tags>Acme, site analysis, parcels</Tags>
</DocumentInfo>
EOF

cat > map.aprx.src/map/roads.json << 'EOF'
{
  "type": "CIMFeatureLayer",
  "name": "Roads",
  "visible": true,
  "renderer": {
    "type": "CIMSimpleRenderer",
    "symbol": { "color": [130, 130, 130], "width": 1.5 }
  }
}
EOF

cat > map.aprx.src/map/parcels.json << 'EOF'
{
  "type": "CIMFeatureLayer",
  "name": "Parcels",
  "visible": true,
  "renderer": {
    "type": "CIMSimpleRenderer",
    "symbol": { "color": [210, 230, 190], "outlineColor": [100, 120, 80] }
  }
}
EOF

# Create the initial .aprx binary from the src directory
python3 - << 'PYEOF'
import zipfile, json, io
from pathlib import Path

src = Path("map.aprx.src")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            name = f.relative_to(src).as_posix()
            content = f.read_bytes()
            if name.endswith(".json"):
                content = json.dumps(json.loads(content), separators=(",", ":")).encode()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(info, content, zipfile.ZIP_DEFLATED, 6)
buf.seek(0)
Path("map.aprx").write_bytes(buf.getvalue())
print("Created map.aprx")
PYEOF

# ── Pre-commit hook — packs .aprx.src → .aprx automatically ───────────────────

mkdir -p .git/hooks
cat > .git/hooks/pre-commit << 'HOOKEOF'
#!/usr/bin/env bash
# managed-by: aprx-tools
set -euo pipefail

STAGED_SRC=$(git diff --cached --name-only | grep '\.aprx\.src' || true)
if [[ -z "$STAGED_SRC" ]]; then exit 0; fi

echo "[aprx-tools] Packing map.aprx.src/ → map.aprx"

python3 - << 'PYEOF'
import zipfile, json, io
from pathlib import Path

src = Path("map.aprx.src")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            name = f.relative_to(src).as_posix()
            content = f.read_bytes()
            if name.endswith(".json"):
                content = json.dumps(json.loads(content), separators=(",", ":")).encode()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(info, content, zipfile.ZIP_DEFLATED, 6)
buf.seek(0)
Path("map.aprx").write_bytes(buf.getvalue())
PYEOF

git add map.aprx
echo "[aprx-tools] ✓ map.aprx updated and staged"
HOOKEOF
chmod +x .git/hooks/pre-commit

# ── Initial commit ─────────────────────────────────────────────────────────────

git add .
git commit -qm "Initial map project: roads and parcels"

# ── feature/add-properties-layer ──────────────────────────────────────────────
# Adds a new properties layer and references it in GISProject.json

git checkout -q -b feature/add-properties-layer

cat > map.aprx.src/map/properties.json << 'EOF'
{
  "type": "CIMFeatureLayer",
  "name": "Properties",
  "visible": true,
  "renderer": {
    "type": "CIMSimpleRenderer",
    "symbol": { "color": [255, 200, 100], "outlineColor": [180, 120, 40] }
  }
}
EOF

python3 - << 'PYEOF'
import json
from pathlib import Path

p = Path("map.aprx.src/GISProject.json")
data = json.loads(p.read_text())
data["title"] = "Acme Site Analysis — New Layers"
data["layers"].append("CIMPATH=map/properties.json")
p.write_text(json.dumps(data, indent=2))
PYEOF

git add map.aprx.src/
git commit -qm "Add properties layer to site analysis"

# ── feature/update-symbology (branches from main, NOT from feature above) ──────
# Updates the title and adds a boundaries layer — will conflict with the above

git checkout -q main

git checkout -q -b feature/update-symbology

python3 - << 'PYEOF'
import json
from pathlib import Path

p = Path("map.aprx.src/GISProject.json")
data = json.loads(p.read_text())
data["title"] = "Acme Site Analysis — Q2 2026"
data["layers"].insert(0, "CIMPATH=map/boundaries.json")
p.write_text(json.dumps(data, indent=2))
PYEOF

cat > map.aprx.src/map/boundaries.json << 'EOF'
{
  "type": "CIMFeatureLayer",
  "name": "Boundaries",
  "visible": true,
  "renderer": {
    "type": "CIMSimpleRenderer",
    "symbol": { "color": [50, 80, 200], "width": 2.0, "style": "dash" }
  }
}
EOF

git add map.aprx.src/
git commit -qm "Add boundaries layer and update Q2 title"

# ── Back to main, ready for the demo ──────────────────────────────────────────

git checkout -q main

# ── also need boundaries.json available on main for the commit to work ─────────
# (the merge will bring it in, but properties.json won't exist on main yet —
#  we copy it here so the resolve step can add both layer files cleanly)

echo ""
echo "Demo repo ready: $DEMO_DIR"
echo ""
echo "Branches:"
git log --oneline --graph --all
echo ""
echo "To record the demo:  cd presentation && vhs demo.tape"
echo "To run manually:     cd $DEMO_DIR"
