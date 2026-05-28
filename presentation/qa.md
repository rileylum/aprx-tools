# Q&A Prep

---

## Language and implementation

**What language is it written in?**
Python, standard library only — `zipfile`, `json`, `xml.etree`. No external dependencies for the core tool. The hooks are plain bash scripts that call Python.

**How does explode work?**
An `.aprx` is a standard zip file, so explode is just `zipfile.extractall` with a formatting pass on top — JSON is pretty-printed with 2-space indent, XML is reformatted with `ElementTree.indent()`. No transformation of the data, purely cosmetic. Files land in `<name>.aprx.src/`.

**How does pack work?**
Reads every file from the `.aprx.src/` directory, minifies JSON (strips all whitespace), leaves XML as-is, then writes a new zip with all timestamps set to `1980-01-01 00:00:00` — the DOS epoch, which is exactly what ArcGIS does natively. That timestamp zeroing is what makes the binary deterministic: same content always produces the same bytes.

**Why does the round-trip produce an identical binary?**
Because we mirror ArcGIS's own conventions exactly: minified JSON, zeroed timestamps, `ZIP_DEFLATED` at compression level 6. The tests verify this — `compare(original, pack(explode(original)))` always returns no differences.

---

## Git hooks

**How do you actually create git hooks?**
Git looks for executable scripts in `.git/hooks/` named after the hook event. Any script placed there and marked executable will be called automatically by git at the right moment. `aprx install` (or npm's postinstall) just writes those scripts — no git configuration needed.

**Which git events trigger the hooks?**
Two: `pre-commit` and `post-stash`. Pre-commit fires before every `git commit`. Post-stash fires after `git stash pop`.

**What does the pre-commit hook actually do?**
It has two steps that always both run:
1. If a `.aprx` file is staged → explode it to `.aprx.src/`, stage the src files, unstage the binary.
2. If any `.aprx.src/` files are staged → pack them into `.aprx`, stage the binary.

Step 2 always runs even if step 1 didn't, which covers merge conflict resolution: you fix the JSON, stage the src files, and the hook automatically produces a fresh `.aprx` without you having to think about it.

**Why does the hook need to modify the staging area?**
Because we want both the `.aprx` binary and the `.aprx.src/` directory in every commit, kept in sync atomically. The hook calls `git add` and `git reset HEAD` on specific files to manage this — it's the same technique linters use when they auto-fix and re-stage code in pre-commit hooks.

**What does the post-stash hook do?**
After `git stash pop` restores `.aprx.src/` files, the `.aprx` binary on disk is still the old version (stash only restores what was stashed). The post-stash hook repacks any `.aprx.src/` directory it finds, keeping the binary in sync.

---

## Workflow and edge cases

**Does every developer need to install this?**
Yes, for contributing changes. Cloning and opening the project works for anyone — the `.aprx` binary is always committed — but without the hooks, commits to the `.aprx` won't update the `.src/` files. npm's postinstall makes hook installation zero-step if the project already uses Node.

**What if someone commits without the hooks?**
The `.aprx` and `.src/` will drift out of sync. `aprx compare` can detect this. The next person to open the project in ArcGIS Pro is fine (they use the binary), but the git history for the src files becomes misleading.

**Does ArcGIS Pro still open the project normally?**
Completely. Pack produces a standard zip with valid CIM JSON. ArcGIS Pro doesn't care about whitespace, and the zeroed timestamps are the same convention ArcGIS uses itself. Pro can't tell the difference between a project it saved and one we packed.

**Does this version control the data too?**
No. The `.aprx` stores references to data sources — connection strings and paths — not the data itself. What you're versioning is the project configuration: which layers exist, how they're symbolised, what the layouts look like.

**What if two people have different versions of ArcGIS Pro?**
When a newer version of Pro upgrades the CIM schema on save, that shows up as a field change in `GISProject.json` — visible and reviewable in the diff rather than buried in a binary. That's actually better than before.

**What about very large projects?**
Each layer gets its own JSON file, so larger projects just produce more files in the src directory. Git handles this well. No practical limit.
