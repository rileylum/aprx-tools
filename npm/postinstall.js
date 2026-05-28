#!/usr/bin/env node
"use strict";

/**
 * Runs after `npm install`. Writes aprx-tools git hooks into the repository
 * that contains this package.json (walking up from __dirname until a .git dir
 * is found). The hooks themselves delegate to `python3 -m aprx_tools`, so
 * the Python package must also be installed for the hooks to function.
 */

const fs   = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const MARKER = "managed-by: aprx-tools";

const HOOKS = {
  "pre-commit": `#!/usr/bin/env bash
# ${MARKER}
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)

PYTHON=python3
for candidate in \\
    "$REPO_ROOT/.venv/bin/python3" \\
    "$REPO_ROOT/venv/bin/python3"  \\
    "$REPO_ROOT/env/bin/python3";  \\
do
    if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
done

"$PYTHON" -m aprx_tools hook pre-commit || {
    echo "aprx-tools: hook failed — is aprx-tools installed? (pip install aprx-tools)" >&2
    exit 1
}
`,

  "post-stash": `#!/usr/bin/env bash
# ${MARKER}
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)

PYTHON=python3
for candidate in \\
    "$REPO_ROOT/.venv/bin/python3" \\
    "$REPO_ROOT/venv/bin/python3"  \\
    "$REPO_ROOT/env/bin/python3";  \\
do
    if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
done

"$PYTHON" -m aprx_tools hook post-stash || true
`,
};

function findGitRoot(start) {
  let dir = start;
  while (true) {
    if (fs.existsSync(path.join(dir, ".git"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null;   // reached filesystem root
    dir = parent;
  }
}

function installHooks() {
  // npm sets INIT_CWD to the directory where `npm install` was run.
  const startDir = process.env.INIT_CWD || process.cwd();
  const gitRoot = findGitRoot(startDir);

  if (!gitRoot) {
    console.log("aprx-tools: not inside a git repository — skipping hook installation");
    return;
  }

  const hooksDir = path.join(gitRoot, ".git", "hooks");
  fs.mkdirSync(hooksDir, { recursive: true });

  for (const [name, content] of Object.entries(HOOKS)) {
    const hookPath = path.join(hooksDir, name);

    if (fs.existsSync(hookPath)) {
      const existing = fs.readFileSync(hookPath, "utf8");
      if (!existing.includes(MARKER)) {
        console.log(
          `aprx-tools: ${name} hook already exists and is not ours — skipping.\n` +
          `  To integrate manually, add this line to ${hookPath}:\n` +
          `    python3 -m aprx_tools hook ${name}`
        );
        continue;
      }
    }

    fs.writeFileSync(hookPath, content, { mode: 0o755 });
    console.log(`aprx-tools: installed ${name} hook`);
  }
}

try {
  installHooks();
} catch (err) {
  // Hook installation failure must not break npm install.
  console.warn(`aprx-tools: hook installation failed — ${err.message}`);
}
