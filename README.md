# aprx-tools

Version-control tooling for ArcGIS `.aprx` project files.

An `.aprx` file is a zip archive of JSON and XML. This tool explodes it into
a diffable directory (`.aprx.src/`), packs it back, and installs git hooks so
the process is automatic.

## How it works

```
map.aprx  ──explode──▶  map.aprx.src/
                           ├── GISProject.json
                           ├── Index.json
                           ├── Layers/
                           │   ├── LGA_Boundaries.json
                           │   └── ...
                           └── Metadata/

map.aprx.src/  ──pack──▶  map.aprx
```

Both `map.aprx` and `map.aprx.src/` are committed. The `.aprx` is marked
binary in `.gitattributes` so git never attempts a text merge on the zip.
Merge conflicts are resolved in the JSON source files; the pre-commit hook
regenerates the `.aprx` automatically.

## Installation

Install via **pip** or any Python package manager:

```sh
pip install aprx-tools
```

Or install via **npm** (also installs the git hooks automatically):

```sh
npm install aprx-tools
```

Requires Python 3.9+. No specific package manager is required in your project
— the installed hooks use whatever Python interpreter is available in your
environment.

## Usage

```sh
# Install git hooks into the current repository
aprx install

# Manually explode or pack
aprx explode map.aprx          # → map.aprx.src/
aprx pack    map.aprx.src/     # → map.aprx

# Compare two .aprx files (or directories) semantically
aprx compare a.aprx b.aprx
```

After `aprx install`, the workflow is automatic:

- **`git add map.aprx && git commit`** — the pre-commit hook explodes the
  `.aprx`, stages the source files, and commits both.
- **`git stash pop`** — the post-stash hook repacks `map.aprx.src/` so your
  local `.aprx` stays in sync.
- **`git pull` / branch switch** — git updates `map.aprx` directly since it
  is a tracked file.

## Roadmap

### Format support

**`.stylx` support**
`.stylx` files are SQLite databases, not ZIPs — no existing textconv hack reaches them. The plan is to dump each symbol definition to an individual JSON file in a `.stylx.src/` directory, making style libraries fully diffable and mergeable.

**`.atbx` support**
ArcGIS toolboxes use the same ZIP-of-JSON structure as `.aprx`. The explode/pack logic already handles this; wiring up the hooks and CLI for `.atbx` is a low-effort extension that gives developer-focused GIS teams version control over their toolbox logic alongside their project files.

### Deployment

**Connection string substitution**
`.aprx` files embed connection strings directly in the JSON — `SERVER=dev-gis;DATABASE=acme_dev` and so on. A `connections.json` file per branch (`.env`-style) would be applied at pack time to substitute all data sources, making branch-per-environment workflows safe without manual `updateConnectionProperties()` scripting on every deploy.

**Broken data source detection**
The pre-commit hook already reads the staged JSON. It can scan connection strings for known-bad patterns (localhost references, dev server names, missing paths) and fail the commit with a clear message before a broken project reaches the remote. Zero additional dependencies.

### Sharing

**Layer export to `.lyrx`**
`.lyrx` files are self-contained, portable layer packages — the standard way to share a layer's symbology, definition query, and data source with another team or project. Because the layer JSON inside an `.aprx` uses the same CIM schema as a standalone `.lyrx`, aprx-tools can export individual layers without ArcPy: `aprx export-layer map.aprx LGA_Boundaries`. This is not a version control strategy (layouts, map settings, bookmarks, and connections are not in `.lyrx`), but it is a useful packaging step when a colleague needs a specific layer rather than the whole project.

### Diffing and history

**`aprx diff` CLI**
`aprx diff a.aprx b.aprx` — a human-readable summary of structural changes between two project files or two git refs. Covers the four things teams actually want: layers added/removed/reordered, connection strings changed, definition queries changed, title/metadata changed. Does not require ArcPy.

**`aprx compare` against git history**
A wrapper around `git diff` that formats output for GIS users rather than showing raw JSON. `aprx log` or `aprx show HEAD~3` — answers "what changed in this project over the last week" in terms of layers and symbology, not JSON keys.

**CI diff reporting**
A GitHub Actions step (or generic CI script) that posts a structured diff as a PR comment: which layers were added, which connection strings changed, which definition queries were modified. Makes map project changes reviewable in the same workflow as code changes, without requiring reviewers to open ArcGIS Pro.

## Contributing

This project uses [uv](https://github.com/astral-sh/uv) for development.
Install it first, then run:

```sh
make dev-setup   # creates the venv, installs dependencies, installs dev hooks
make test        # run the test suite
```

`uv` is only required to work on `aprx-tools` itself. Projects that install
the package are free to use pip, conda, poetry, or any other tool.
