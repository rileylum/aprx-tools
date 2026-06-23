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

## Two modes

aprx-tools runs in one of two modes. **You never pass a flag to choose between
them — the mode is detected automatically from which configuration files are
present** in the project (see [How the mode is detected](#how-the-mode-is-detected)).

| | **Simple mode** | **Environment mode** |
|---|---|---|
| **When** | default — no config files present | opt-in — `aprx.json`, `connections/`, or `local.json` present |
| **Setup** | none — just `aprx install` | `aprx connections init` + per-environment files (see [Setup](#setup)) |
| **Connection strings** | stored verbatim in the committed source | stored as `@@tokens@@`; real values live in per-environment files |
| **`explode` does** | pretty-print JSON/XML | pretty-print **+** reverse-tokenise values → `@@tokens@@` |
| **`pack` does** | minify JSON | minify **+** substitute `@@tokens@@` → values for one environment |
| **Committed** | both `map.aprx` and `map.aprx.src/` | `map.aprx.src/` **+** `connections/<env>.json`; the `.aprx` is gitignored |
| **Built for** | one shared binary | a separate binary per environment, built on demand |

Simple mode is the original behaviour and stays the default. If you have never run
`aprx connections init` (and have no `aprx.json`, `connections/`, or `local.json`),
the tool behaves exactly as a plain explode/pack round-trip with no substitution of
any kind.

### How the mode is detected

On every `explode` and `pack`, the tool walks up from the `.aprx` (explode) or the
`.aprx.src/` directory (pack) toward the git root, looking for any one of these
opt-in markers:

- **`aprx.json`** — which fields to tokenise and the token format
- a **`connections/`** directory — one `*.json` per environment
- a **`local.json`** — the developer's working connections

Finding **none** of them → **simple mode**. Finding **any** of them → **environment
mode**. The search stops at the first marker found, or at the git root. Because the
trigger is the *presence of a file you added deliberately*, you cannot fall into
environment mode by accident — and adding the files is the only thing that turns it
on.

## Installation

Requires **Python 3.9+**. The Python package is the real tool; the npm package is
only a convenience wrapper that installs the git hooks (see the caveat below).

### From PyPI

```sh
pip install aprx-tools          # or: uv pip install / pipx install aprx-tools
```

### From source

Works without waiting on a release — install straight from the repository:

```sh
# directly from GitHub
pip install "git+https://github.com/rileylum/aprx-tools.git"

# or from a local clone (use -e for an editable/dev install)
git clone https://github.com/rileylum/aprx-tools.git
cd aprx-tools
pip install .
```

### Via npm

```sh
npm install aprx-tools
```

> **The npm package does not include the tool itself.** It ships only the hook
> installer, which shells out to `python3 -m aprx_tools`. You must **also** have the
> Python package installed (`pip install aprx-tools`) and Python 3.9+ on `PATH`, or
> the hooks will fail. Use npm only if you want the hooks wired up as part of an
> existing Node project's `install` step.

After installing, run `aprx install` in your repository to set up the git hooks. No
specific package manager is required in your project — the hooks use whatever Python
interpreter is available in your environment.

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

## Environment mode (connection strings)

This is the setup and detail for **environment mode** — the opt-in mode from
[Two modes](#two-modes). If you only need a diffable, version-controlled `.aprx`
and do not promote across environments, you do **not** need any of this; stay in
simple mode (just `aprx install`).

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

Run these steps once per project. **Step 1 is what switches the project into
environment mode** — it creates `aprx.json` and `connections/`, which the detector
keys off (see [How the mode is detected](#how-the-mode-is-detected)).

**1. Scaffold the config from the existing `.aprx`:**

```sh
aprx connections init map.aprx
```

This scans the project and writes three files:

| File | Purpose |
|------|---------|
| `aprx.json` | which fields to substitute (default `workspaceConnectionString`) + token format |
| `connections/dev.json` | a generated key for every distinct connection string, with the real values it found |
| `local.json.example` | a template for each developer's own `local.json` |

**2. Tell git which files are environment-specific or per-developer:**

```sh
echo "local.json" >> .gitignore   # per-developer, never committed
echo "*.aprx"      >> .gitignore   # derived artifact, built on demand
```

**3. Create your working connections and the other environments:**

```sh
cp local.json.example local.json          # fill in your local paths
# add connections/uat.json, connections/prd.json — same keys as dev.json
aprx connections check                     # assert every env defines the same keys
```

**4. Re-explode so the committed source becomes tokenised:**

```sh
aprx explode map.aprx                       # connection strings become @@tokens@@
```

From here the hooks take over: commit stages only the tokenised source, and
`aprx build` / the post-merge hook rebuild your working `.aprx` from source +
`local.json`.

### What actually gets replaced (and what doesn't)

Being in environment mode does **not** mean every command always substitutes.
Tokenising (explode) and substituting (pack) each have their own trigger:

- **`explode` tokenises** only when there is at least one connection file *with
  values* — any `connections/*.json` or a `local.json`. Values found in those files,
  appearing in a configured field, become `@@tokens@@`. A connection string that is
  **not** registered in any file is a hard error (so nothing leaks in untokenised).
- **`pack` substitutes** only when it can resolve a single connection file to use, in
  this precedence: `--connections FILE` > `--env NAME` (→ `connections/NAME.json`) >
  `local.json`. If none of these resolves, pack leaves the source **unchanged** —
  even in environment mode.

Two consequences worth knowing:

- An **empty `connections/` directory** (no `*.json`, no `local.json`) puts the
  project in environment mode but supplies no values: explode tokenises nothing and
  pack substitutes nothing. The one visible effect is that `--env uat` becomes a hard
  error (`connections/uat.json` doesn't exist) instead of a silent no-op.
- If you have `connections/*.json` but **no `local.json`**, a bare `aprx pack dir`
  (no `--env`/`--connections`) does not substitute — it would leave `@@tokens@@`
  literals in the binary. Build for a specific environment with `--env`, or keep a
  `local.json` for day-to-day work.

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
- **CI** verifies every PR with `aprx verify` and builds the environment-specific
  artifact with `aprx pack map.aprx.src --env uat`, never reading the committed
  binary. See [Continuous integration](#continuous-integration).

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

## Continuous integration

The CI gate is a single command — **`aprx verify`** — that exits non-zero on
failure. It is not GitHub-specific: it is a plain CLI check, so any runner invokes
it the same way. For an environment-managed project it asserts the committed source
is fully tokenised (nobody committed without the hooks) and that every token
resolves in every `connections/<env>.json` (the project builds for each
environment). For a simple project it asserts the committed `.aprx` is in sync with
its source.

The job body is identical everywhere — `pip install aprx-tools && aprx verify` —
only the trigger differs:

**GitHub Actions** — `.github/workflows/aprx.yml`

```yaml
name: aprx
on: [pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.x" }
      - run: pip install aprx-tools
      - run: aprx verify
```

**GitLab CI** — `.gitlab-ci.yml`

```yaml
aprx-verify:
  image: python:3
  script:
    - pip install aprx-tools
    - aprx verify
```

**Azure Pipelines** — `azure-pipelines.yml`

```yaml
steps:
  - script: |
      pip install aprx-tools
      aprx verify
    displayName: aprx verify
```

**Any other runner** (Bitbucket, Jenkins, pre-commit.ci, a local pre-push) — just
run the command:

```sh
pip install aprx-tools && aprx verify
```

The same gate runs **locally as a `pre-push` hook** (installed by `aprx install`), so
you catch a drifted or incomplete-across-environments source before it leaves your
machine instead of on a red PR — `git push --no-verify` bypasses it for an
intentional work-in-progress push.

Pair the CI check with a branch-protection rule requiring it to pass and hook
installation becomes effectively mandatory — someone can bypass the hooks locally
but cannot merge a drifted or unbuildable source. To deploy, add a step that builds
the target environment's artifact and publishes it:

```sh
aprx pack map.aprx.src --env "$TARGET_ENV" -o map.aprx   # then upload map.aprx
```

## Releasing

Publishing is automated by
[`.github/workflows/release.yml`](.github/workflows/release.yml): publishing a
GitHub Release builds and uploads the Python package to PyPI and the hook installer
to npm.

### One-time setup

- **PyPI** uses trusted publishing (OIDC) — no API token is stored. On PyPI, add a
  *pending* publisher for project `aprx-tools` → owner `rileylum`, repository
  `aprx-tools`, workflow `release.yml`, environment `pypi`. (It is *pending* because
  the project does not exist on PyPI until the first upload.)
- **npm** uses a token. Create an npm automation (or granular write) token for the
  package and add it to the repository as the `NPM_TOKEN` secret.

### Cutting a release

1. Bump the version in **all three** places — they must stay in sync:
   `pyproject.toml`, `package.json`, and `aprx_tools/__init__.py`.
2. Commit, then publish a GitHub Release whose tag is the version prefixed with `v`
   (e.g. `v0.1.0`). The `release` workflow does the rest.

Both registries reject re-uploading an existing version, so every release needs a
fresh version number.

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

**Connection string enforcement**
`aprx verify` already catches hookless commits and unbuildable environments (see
[Continuous integration](#continuous-integration)). The remaining piece is *policy*:
asserting connection strings match the expected pattern for the target branch — dev
must not reference prod servers, prod must not reference localhost — to catch the
wrong-environment deployment error before it reaches the environment.

**Automated connection string substitution on push**
The substitution itself now ships (see [Environment mode](#environment-mode-connection-strings));
`aprx pack --env <name>` applies
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
