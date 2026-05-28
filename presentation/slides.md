---
marp: true
theme: default
paginate: true
style: |
  :root {
    --color-background: #ffffff;
  }
  section {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #ffffff;
    color: #1a1a2e;
    padding: 48px 64px;
  }
  section.lead {
    background: #0f3460;
    color: #ffffff;
    justify-content: center;
  }
  section.lead h1 { color: #ffffff; font-size: 2.4em; }
  section.lead h3 { color: #c8e6f0; font-weight: 400; }
  section.lead p  { color: #c8e6f0; font-size: 0.9em; margin-top: 2em; }
  section.lead code { background: rgba(255,255,255,0.18); color: #ffffff; border: 1px solid rgba(255,255,255,0.3); }
  h1 { color: #0f3460; font-size: 1.8em; border-bottom: 3px solid #e94560; padding-bottom: 8px; }
  h2 { color: #0f3460; }
  strong { color: #c0183a; }
  strong code { color: #c0183a; }
  code { background: #dde4f0; border-radius: 3px; padding: 1px 5px; font-size: 0.9em; color: #1a1a2e; }
  pre { background: #1a1a2e; border-radius: 8px; padding: 24px; }
  pre code { background: transparent; color: #e0eaf5; font-size: 0.82em; padding: 0; border: none; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2em; }
  ul { line-height: 1.9; }
  li { margin: 0; }
---

<!-- _class: lead -->

# Version Controlling<br>ArcGIS Projects

### Transparent, automatic, mergeable `.aprx` management

Acme Geospatial · May 2026

---

# The Problem

Two GIS developers. One project. Separate feature branches.

<br>

```
$ git merge feature/add-layer

warning: Cannot merge binary files: project.aprx
CONFLICT (binary): Merge conflict in project.aprx
Automatic merge failed; fix conflicts and then commit the result.
```

<br>

No diff. No context. **No way to see what changed.**

**Last commit wins.**

---

# Problem 1 — Merge Conflicts

<div class="columns">
<div>

Alice adds a new layer to `project.aprx` on her branch.

Bob updates the symbology on his branch.

They both try to merge to `main`.

**One of them loses their work.**

</div>
<div>

```
main
 │
 ├─ feature/alice-new-layer
 │    └ project.aprx  ← binary
 │
 └─ feature/bob-symbology
      └ project.aprx  ← binary
```

Git can't merge two binary files.
There is no diff. There is no winner.

</div>
</div>

---

# Problem 2 — Environment Branches

Many projects follow a branch-per-environment workflow:

```
dev ──push──► uat ──push──► trn ──push──► prd
```

But `.aprx` has connection strings **baked into the binary**:

```json
"connectionString": "SERVER=dev-gis;DATABASE=acme_dev;VERSION=dbo.DEFAULT"
```

Push the branch. **Production now queries dev data.**

Style changes and connection strings are **inseparable** in the binary.
You can't cherry-pick just the visual changes.

---

# The Insight

An `.aprx` is just a zip file.

```
project.aprx  (it's a zip)
├── GISProject.json      ← maps, layers, layouts
├── DocumentInfo.xml     ← author, description, tags
└── map/
    ├── roads.json       ← layer definition, renderer, labels
    └── parcels.json     ← symbology, scale ranges, popups
```

It's already **structured JSON and XML data.**

We just need to see it.

---

# The Solution — Explode

```bash
$ aprx explode project.aprx
```

```
project.aprx.src/
├── GISProject.json      ✓  pretty-printed, 2-space indent
├── DocumentInfo.xml     ✓  formatted
└── map/
    ├── roads.json       ✓  human-readable
    └── parcels.json     ✓  human-readable
```

**Track the `.aprx.src/` directory in git.**

Now you can diff it, branch it, merge it, review it.

---

# The Solution — Pack

```bash
$ aprx pack project.aprx.src/
```

```
project.aprx
  ✓  JSON minified          (no whitespace)
  ✓  Timestamps zeroed      (1980-01-01 — same as ArcGIS)
  ✓  Deterministic binary   (same content = same file, every time)
```

ArcGIS Pro opens it like any other project.
The binary is committed alongside the source — no extra steps for the team.

---

# Hooks — Automatic

Developers **never** run `explode` or `pack` manually.

```
git commit
      │
      ▼
  pre-commit hook
      │
      ├── .aprx staged?    →  explode → stage .aprx.src/ files
      │                        (replaces the binary in the index)
      │
      └── .aprx.src staged? →  pack → stage .aprx
                               (always runs — covers merge resolution too)
      │
      ▼
  Both committed atomically.
```

`post-stash` hook repacks after `git stash pop`.

---

# Install

<div class="columns">
<div>

**Node** — hooks install automatically

```bash
npm install aprx-tools
```

That's it. `postinstall` wires<br>up the git hooks.

</div>
<div>

**Python**

```bash
pip install aprx-tools
aprx install
```

Or with uv:

```bash
uv add aprx-tools
aprx install
```

</div>
</div>

<br>

Hooks detect a venv automatically — no path config needed.

---

<!-- _class: lead -->

# Demo

Merge conflict → human-readable resolution

`feature/add-properties-layer` + `feature/update-symbology` → `main`

---

# What's Next

- **Connection string substitution** — `connections.json` per branch, substituted at pack time (`.env` for ArcGIS)
- **CI diff reporting** — PR comment showing what changed in each layer
- **ArcGIS Pro extension** — explode/pack from within the application

<br>

Open source:

```
github.com/rileylum/git-aprx
```

```bash
npm install aprx-tools
```
