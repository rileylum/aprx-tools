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

## Environment-specific connection strings

`.aprx` files embed database connection strings directly in their JSON. Teams that
promote work across environment branches (dev → uat → prd) need each environment to
point at its own database — but those connection strings would otherwise travel with
every merge and break deploys, forcing a manual "fix the connections" commit after
each promotion.

aprx-tools solves this by keeping the committed source **environment-neutral**:
connection strings are stored as `@@tokens@@`, and the real values live in
per-environment files. `pack` substitutes tokens → values for a chosen environment;
`explode` reverse-tokenises values → tokens.

### Setup

```sh
aprx connections init map.aprx
```

This scans the project, generates a key for each distinct connection string, and
writes `aprx.json` (which fields to substitute), `connections/dev.json` (the real
values it found), and `local.json.example` (a template). Then:

```sh
echo "local.json" >> .gitignore   # per-developer, never committed
echo "*.aprx"      >> .gitignore   # derived artifact, built on demand

cp local.json.example local.json   # fill in your local paths
# add connections/uat.json, connections/prd.json with the same keys
aprx explode map.aprx              # connection strings become @@tokens@@
```

### How it fits together

| File | Committed? | Holds |
|------|-----------|-------|
| `map.aprx.src/` | yes | environment-neutral source (tokens) — the source of truth |
| `connections/<env>.json` | yes | real connection strings, one file per environment |
| `local.json` | no (gitignored) | each developer's working connections |
| `map.aprx` | no (gitignored) | working / deploy binary, built on demand |

- **Developers** open a working `map.aprx` built from the source + their `local.json`.
  The `post-merge` / `post-checkout` hooks rebuild it automatically after pulls and
  branch switches; `aprx build` does it manually.
- **On commit**, the pre-commit hook re-explodes the working `.aprx`, re-tokenising
  it, and stages only the neutral source — the binary is never committed.
- **CI** builds the environment-specific artifact with `aprx pack map.aprx.src --env uat`
  and never reads the committed binary:

  ```yaml
  # .github/workflows/deploy.yml (sketch)
  - run: pip install aprx-tools
  - run: aprx connections check                    # every env defines the same keys
  - run: aprx pack map.aprx.src --env uat -o map.aprx
  # → publish map.aprx to the UAT portal
  ```

Because connection strings never live in the merged content, a PR merge can't carry
the wrong ones. A connection string with no registered key fails the explode; a
missing key fails the pack — so a wrong-environment build fails loudly instead of
publishing against the wrong database.

### Configurable fields

By default only `workspaceConnectionString` is substituted. To cover other
environment-specific fields (e.g. service URLs), list them in `aprx.json`:

```json
{ "fields": ["workspaceConnectionString", "serviceUrl"] }
```

## Roadmap

### Format support

**`.stylx` support**
`.stylx` files are SQLite databases, not ZIPs — no existing textconv hack reaches them. The plan is to dump each symbol definition to an individual JSON file in a `.stylx.src/` directory, making style libraries fully diffable and mergeable.

**`.atbx` support**
ArcGIS toolboxes use the same ZIP-of-JSON structure as `.aprx`. The explode/pack logic already handles this; wiring up the hooks and CLI for `.atbx` is a low-effort extension that gives developer-focused GIS teams version control over their toolbox logic alongside their project files.

### Deployment

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

### CI/CD and automation

**`gitattributes` textconv**
A `.gitattributes` entry that tells GitHub to run `aprx explode` as a textconv driver when rendering diffs. GitHub's PR UI shows the JSON diff inline instead of "binary file changed". No CI required — just config. The lowest-effort improvement available to any team adopting the tool today.

**Sync validation**
A CI job that verifies the committed `.aprx` binary matches what you'd get by packing the committed `.aprx.src/` — i.e. `aprx compare map.aprx map.aprx.src/` passes. Catches commits made without hooks installed. Pair with a branch protection rule requiring the check to pass and hook installation becomes effectively mandatory: people can bypass locally but cannot merge a drifted binary.

**Connection string enforcement**
A CI check that reads connection strings from `.aprx.src/` and asserts they match the expected pattern for the target branch — dev branch must not reference prod servers, prod branch must not reference localhost. Catches the wrong-environment deployment error before it reaches the environment.

**Automated connection string substitution on push**
The substitution itself now ships (see [Environment-specific connection
strings](#environment-specific-connection-strings)); `aprx pack --env <name>` applies
a branch's connection file at pack time. What remains is the packaging glue: a
GitHub Actions workflow on push to environment branches (`uat`, `trn`, `prd`) that
runs the build and publishes the artifact, so no developer has to remember to do it
manually on each deploy.

**Deployment artifact / Portal publish**
After substitution, pack an environment-specific `.aprx` and upload it as a build artifact or publish directly to ArcGIS Enterprise / Portal via the REST API. Closes the last manual step in the promotion pipeline.

The full pipeline once these pieces exist:

```
developer commits  →  pre-commit hook        →  explodes, packs, stages
PR opened          →  CI sync check          →  binary matches src?
                   →  CI diff comment        →  what changed in this PR?
                   →  CI connection check    →  no prod strings on dev branch?
PR merged to uat   →  CI substitution + pack →  uat connection strings applied
                   →  artifact / deploy      →  published to UAT portal
```

Local hooks and CI checks are defence-in-depth for the same invariants — someone without hooks installed gets caught by CI before they can merge.

## Testing

The test suite covers the core explode/pack/compare/install workflows against a single Pro 3.x fixture. The following areas need additional coverage before the tool can be considered production-ready.

### Version fixtures

The current fixture is Pro 3.x (JSON internals). Pro 2.x stored internals as XML — a breaking schema change at the 3.0 boundary. A round-trip test against a real Pro 2.x project (targeting ~2.9, the last XML-based release) and a Pro 3.0 project (first JSON-based release) would verify the tool handles both formats correctly or fails gracefully at the boundary. Acquiring these fixtures requires access to older Pro installs.

### Binary pass-through

`.aprx` files can contain non-JSON/XML entries — thumbnail images (`.dat` files in a `Thumbnails/` folder) and other binary blobs. These must be copied verbatim without any formatting or parsing attempt. There are currently no tests verifying this; a malformed binary-as-text path would silently corrupt the packed output.

### Determinism

The round-trip test confirms semantic identity (`compare` returns no diff). The stronger guarantee — that two independent pack runs from the same source produce byte-for-byte identical output — is not explicitly tested. A test packing the same directory twice and asserting `bytes_a == bytes_b` would catch non-determinism from dictionary ordering, file enumeration order, or timestamp handling.

### Cross-platform

The test suite runs on Linux only. The two most likely Windows/macOS failure points are CIMPATH URI construction (forward slashes must be preserved regardless of OS path separator) and XML line ending normalisation (which could break determinism across platforms). The existing tests are written to catch both — running them in a CI matrix across Linux, Windows, and macOS is the main gap, not new test logic.

### Structural variations

The current fixture has feature layers, a table, a basemap, and a layout. Missing coverage:

- **Multiple maps** — a project containing two or more maps, exercising CIMPATH reference resolution across the layer tree
- **Deeply nested group layers** — verifies child layer ordering is preserved through round-trip
- **Empty/minimal project** — no layers, no layout; confirms the tool does not crash on degenerate input
- **Non-ASCII content** — Unicode in layer names or connection strings

### Hook behaviour under failure

The install tests cover hook wiring. Not covered: what happens when pack is invoked on malformed JSON (e.g. a file mid-merge-conflict with conflict markers). The hook should fail the commit with a readable error rather than a Python traceback or — worse — silently succeed with a broken binary.

## Contributing

This project uses [uv](https://github.com/astral-sh/uv) for development.
Install it first, then run:

```sh
make dev-setup   # creates the venv, installs dependencies, installs dev hooks
make test        # run the test suite
```

`uv` is only required to work on `aprx-tools` itself. Projects that install
the package are free to use pip, conda, poetry, or any other tool.
