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

## Contributing

This project uses [uv](https://github.com/astral-sh/uv) for development.
Install it first, then run:

```sh
make dev-setup   # creates the venv, installs dependencies, installs dev hooks
make test        # run the test suite
```

`uv` is only required to work on `aprx-tools` itself. Projects that install
the package are free to use pip, conda, poetry, or any other tool.
