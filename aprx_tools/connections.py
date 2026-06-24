"""Environment-aware connection-string substitution.

The committed ``.aprx.src/`` is environment-neutral: configured fields (default
``workspaceConnectionString``) store an ``@@token@@`` placeholder instead of a real
connection string.  The real values live in per-environment connection files.

    explode:  real value  --tokenize-->    @@key@@      (neutral, committed)
    pack:     @@key@@      --substitute-->  real value   (environment-specific build)

Keeping connection strings out of the mergeable content is what lets work flow
dev -> uat -> prd without dragging the wrong database along.

Everything here operates on **parsed JSON objects** rather than text, so values
containing backslashes, semicolons or quotes re-serialise with correct escaping.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_FIELDS = ("workspaceConnectionString",)
DEFAULT_TOKEN = "@@{key}@@"

CONFIG_FILENAME = "aprx.json"
CONNECTIONS_DIR = "connections"
LOCAL_FILE = "local.json"


# --------------------------------------------------------------------------- #
# Project discovery & config
# --------------------------------------------------------------------------- #

def find_project_config(start) -> "Path | None":
    """Walk up from *start* to the git root looking for a project that opts into
    connection substitution.  A directory qualifies if it contains ``aprx.json``,
    a ``connections/`` directory, or a ``local.json``.  Returns that directory, or
    ``None`` (simple mode — no substitution, original behaviour)."""
    start = Path(start).resolve()
    if start.is_file():
        start = start.parent
    for d in (start, *start.parents):
        if (
            (d / CONFIG_FILENAME).exists()
            or (d / CONNECTIONS_DIR).is_dir()
            or (d / LOCAL_FILE).exists()
        ):
            return d
        if (d / ".git").exists():
            break
    return None


def load_config(project_dir) -> dict:
    """Read ``aprx.json`` (fields + token format) with defaults applied."""
    fields = list(DEFAULT_FIELDS)
    token = DEFAULT_TOKEN
    if project_dir is not None:
        cfg_path = Path(project_dir) / CONFIG_FILENAME
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            fields = cfg.get("fields", fields)
            token = cfg.get("token", token)
    if "{key}" not in token:
        sys.exit(f"aprx-tools: token format {token!r} must contain '{{key}}'")
    return {"fields": list(fields), "token": token}


def connection_files(project_dir) -> "list[Path]":
    """All connection files that supply *real* values: ``connections/*.json`` plus
    ``local.json`` if present.  Used to build the reverse map for tokenisation."""
    project_dir = Path(project_dir)
    files = []
    conn_dir = project_dir / CONNECTIONS_DIR
    if conn_dir.is_dir():
        files.extend(sorted(conn_dir.glob("*.json")))
    local = project_dir / LOCAL_FILE
    if local.exists():
        files.append(local)
    return files


def resolve_connections_file(project_dir, env=None, connections_file=None) -> "Path | None":
    """Pick the connection file to apply when packing.

    Precedence (highest first):
      1. ``connections_file`` — explicit path, must exist.
      2. ``env``             — ``connections/<env>.json``, must exist.
      3. default             — ``local.json`` if present.

    An explicitly requested file that is missing is a hard error.  When nothing is
    requested and there is no ``local.json``, returns ``None`` (simple mode)."""
    if connections_file:
        p = Path(connections_file)
        if not p.exists():
            sys.exit(f"aprx-tools: connections file {p} not found")
        return p
    if env:
        if project_dir is None:
            sys.exit("aprx-tools: --env requires a project with a connections/ directory")
        p = Path(project_dir) / CONNECTIONS_DIR / f"{env}.json"
        if not p.exists():
            sys.exit(f"aprx-tools: no connections file for environment {env!r} (expected {p})")
        return p
    if project_dir is not None:
        local = Path(project_dir) / LOCAL_FILE
        if local.exists():
            return local
    return None


# --------------------------------------------------------------------------- #
# Connection maps
# --------------------------------------------------------------------------- #

def load_connections(path) -> "dict[str, str]":
    """Load a ``{key: connection_string}`` JSON object."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        sys.exit(f"aprx-tools: {path} must be a JSON object of key -> connection string")
    return data


def build_reverse_map(files) -> "dict[str, str]":
    """Union of all connection files as ``{connection_string: key}``.

    The same key carrying different values across environments is expected (that is
    the whole point).  The same *value* mapped to two different keys is ambiguous
    and is a hard error."""
    reverse: "dict[str, str]" = {}
    for path in files:
        for key, value in load_connections(path).items():
            existing = reverse.get(value)
            if existing is not None and existing != key:
                sys.exit(
                    f"aprx-tools: connection value {value!r} is mapped to both "
                    f"{existing!r} and {key!r} — a value must map to one key"
                )
            reverse[value] = key
    return reverse


# --------------------------------------------------------------------------- #
# Token <-> value transforms (operate in place on parsed JSON)
# --------------------------------------------------------------------------- #

def _token_regex(token: str) -> "re.Pattern":
    prefix, suffix = token.split("{key}", 1)
    return re.compile("^" + re.escape(prefix) + r"(?P<key>.+?)" + re.escape(suffix) + "$")


def _walk_fields(obj, fields, visit) -> None:
    """The one traversal the four field operations share.

    Descends *obj* depth-first and calls ``visit(node, key, value)`` for every dict
    entry whose key is a configured field carrying a string value — ``node`` is the
    owning dict (so a visitor can rewrite ``node[key]`` in place).  A matched field is
    a leaf: its value is handed to the visitor, not descended into.  Every other
    branch (non-field keys, nested dicts, list items) is recursed.  Tokenize,
    substitute, token scan and value collect differ only in *visit*."""
    fields = set(fields)

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in fields and isinstance(v, str):
                    visit(node, k, v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)


def substitute(obj, key_to_value, fields=DEFAULT_FIELDS, token=DEFAULT_TOKEN):
    """Replace ``@@key@@`` tokens in *fields* with their real values.

    Returns ``(obj, missing_keys)``; a token whose key is absent from
    *key_to_value* is collected in ``missing_keys`` (caller fails fast)."""
    regex = _token_regex(token)
    missing: "set[str]" = set()

    def visit(node, k, v):
        m = regex.match(v)
        if m:
            key = m.group("key")
            if key in key_to_value:
                node[k] = key_to_value[key]
            else:
                missing.add(key)
        # a literal (already-real) value is left untouched

    _walk_fields(obj, fields, visit)
    return obj, missing


def tokenize(obj, value_to_key, fields=DEFAULT_FIELDS, token=DEFAULT_TOKEN):
    """Replace real connection strings in *fields* with their ``@@key@@`` token.

    Returns ``(obj, unknown_values)``; a field value that is neither already a token
    nor present in *value_to_key* is collected in ``unknown_values`` (caller fails
    fast — it means an unregistered connection string)."""
    regex = _token_regex(token)
    unknown: "set[str]" = set()

    def visit(node, k, v):
        if regex.match(v):
            return  # already tokenised
        if v in value_to_key:
            node[k] = token.format(key=value_to_key[v])
        else:
            unknown.add(v)

    _walk_fields(obj, fields, visit)
    return obj, unknown


def collect_field_values(obj, fields=DEFAULT_FIELDS) -> "set[str]":
    """All distinct string values found under *fields* — used by ``connections init``
    to discover the connection strings that need keys."""
    found: "set[str]" = set()

    def visit(node, k, v):
        found.add(v)

    _walk_fields(obj, fields, visit)
    return found


def scan_tokens(obj, fields=DEFAULT_FIELDS, token=DEFAULT_TOKEN):
    """Inspect an already-tokenised source. Returns ``(referenced_keys, raw_values)``:
    keys for field values that are ``@@token@@`` placeholders, and raw_values for
    field values that are *not* tokens — a raw value means a real connection string
    leaked into the committed source (e.g. a commit made without the hooks)."""
    regex = _token_regex(token)
    keys: "set[str]" = set()
    raw: "set[str]" = set()

    def visit(node, k, v):
        m = regex.match(v)
        (keys.add(m.group("key")) if m else raw.add(v))

    _walk_fields(obj, fields, visit)
    return keys, raw
