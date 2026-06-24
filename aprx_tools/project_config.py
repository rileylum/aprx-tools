"""``ProjectConfig`` — the single home for a Project's resolution ritual.

A Project declares its **Mode** once, explicitly, in a committed ``aprx.json``
(``"mode": "simple" | "env"``, alongside ``fields`` and ``token``). ``ProjectConfig``
is the one object that reads that declaration and, for environment-mode Projects,
discovers the connection files and builds the token<->value maps. Every caller that
needs to know "what is this Project and how does it substitute" goes through here, so
the assembly sequence is not copy-pasted across explode / pack / verify / bootstrap.

Resolution is **strict** (ADR-0001): a Project with no ``aprx.json``, or one whose
``aprx.json`` omits ``mode``, is a hard error directing the user to run ``aprx install``.
The old presence-sniffing heuristic (infer env mode from a stray ``connections/`` dir or
``local.json``) is gone — mode is read, never guessed.

Named ``ProjectConfig`` and **not** ``Project``: "Project" is the domain noun for the
ArcGIS project itself (see ``docs/agent/CONTEXT.md``).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import connections as conn

SIMPLE = "simple"
ENV = "env"
MODES = (SIMPLE, ENV)

_INSTALL_HINT = "run `aprx install` to declare it"


def write_mode(config_path, mode: str, existing: "dict | None" = None) -> None:
    """Write *mode* into an ``aprx.json``, ``mode`` first, preserving any other keys
    in *existing* (e.g. the ``fields``/``token`` scaffolded by ``connections init``).

    This is the **single writer** of the ``ProjectConfig``-loadable shape. Both
    ``aprx install`` and ``connections init`` funnel through it so the two paths can
    never emit divergent files: whichever runs second keeps what the first wrote."""
    merged = {"mode": mode}
    merged.update({k: v for k, v in (existing or {}).items() if k != "mode"})
    Path(config_path).write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ProjectConfig:
    """A Project's declared configuration, loaded from its ``aprx.json``.

    Attributes:
        dir:    the Project directory (the one holding ``aprx.json``).
        mode:   ``"simple"`` or ``"env"``.
        fields: the JSON field names whose values are connection strings.
        token:  the placeholder format, e.g. ``"@@{key}@@"``.
    """

    dir: Path
    mode: str
    fields: tuple[str, ...]
    token: str

    # ----------------------------------------------------------------- #
    # Construction — the one place the file is read and validated.
    # ----------------------------------------------------------------- #

    @classmethod
    def load(cls, project_dir) -> "ProjectConfig":
        """Read and validate ``<project_dir>/aprx.json``.

        Strict: a missing file or a missing ``mode`` is a hard error pointing at
        ``aprx install``. Returns a frozen ``ProjectConfig`` on success."""
        project_dir = Path(project_dir)
        cfg_path = project_dir / conn.CONFIG_FILENAME

        if not cfg_path.exists():
            sys.exit(
                f"aprx-tools: {project_dir} has no {conn.CONFIG_FILENAME} — "
                f"this project has no declared mode; {_INSTALL_HINT}"
            )

        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            sys.exit(f"aprx-tools: {cfg_path} is not valid JSON ({err})")
        if not isinstance(cfg, dict):
            sys.exit(f"aprx-tools: {cfg_path} must be a JSON object — {_INSTALL_HINT}")

        if "mode" not in cfg:
            sys.exit(
                f"aprx-tools: {cfg_path} declares no 'mode' — {_INSTALL_HINT}"
            )

        mode = cfg["mode"]
        if mode not in MODES:
            sys.exit(
                f"aprx-tools: {cfg_path} has unknown mode {mode!r} — "
                f"expected one of {', '.join(MODES)}"
            )

        token = cfg.get("token", conn.DEFAULT_TOKEN)
        if "{key}" not in token:
            sys.exit(f"aprx-tools: token format {token!r} must contain '{{key}}'")

        fields = cfg.get("fields", conn.DEFAULT_FIELDS)
        # A bare string would be shredded into characters by tuple(), silently
        # matching no field and leaking raw connection strings — reject it.
        if isinstance(fields, str) or not isinstance(fields, (list, tuple)):
            sys.exit(
                f"aprx-tools: 'fields' in {cfg_path} must be a list of field names"
            )

        return cls(dir=project_dir, mode=mode, fields=tuple(fields), token=token)

    # ----------------------------------------------------------------- #
    # Mode predicate
    # ----------------------------------------------------------------- #

    @property
    def is_env(self) -> bool:
        """True for environment-mode Projects (the ones that substitute)."""
        return self.mode == ENV

    # ----------------------------------------------------------------- #
    # Environment mode — connection discovery & map building.
    # Built lazily: connection files may not exist yet at load time, and
    # explode (reverse) vs pack (forward) want different maps.
    # ----------------------------------------------------------------- #

    def _require_env(self, what) -> None:
        """Mode is the master switch: substitution is meaningless in simple mode,
        so calling an env-only helper there is a hard error rather than a silent
        no-op that might pick up a stray ``local.json``."""
        if not self.is_env:
            sys.exit(
                f"aprx-tools: {self.dir} is a simple-mode project — "
                f"{what} is only available in environment mode"
            )

    def connection_files(self) -> "list[Path]":
        """Every connection file supplying real values: ``connections/*.json``
        plus ``local.json`` if present."""
        self._require_env("connection-file discovery")
        return conn.connection_files(self.dir)

    def reverse_map(self) -> "dict[str, str]":
        """``{connection_string: key}`` unioned across **all** connection files,
        ``local.json`` included. The full union — kept for any caller that genuinely
        wants it; explode does **not** use this (see ``committed_reverse_map``). A
        value mapped to two keys is a hard error."""
        self._require_env("the connection reverse map")
        return conn.build_reverse_map(self.connection_files())

    def committed_connection_files(self) -> "list[Path]":
        """Only ``connections/*.json`` — the **committed**, team-shared environments,
        excluding the gitignored, per-developer ``local.json``."""
        self._require_env("committed connection-file discovery")
        return conn.committed_connection_files(self.dir)

    def committed_reverse_map(self) -> "dict[str, str]":
        """``{connection_string: key}`` unioned across the **committed** environments
        only (``connections/*.json``, never ``local.json``) — used to **tokenize** on
        explode.

        Tokenising against committed files alone is a safety property: a connection
        string that exists only in a developer's ``local.json`` is an *unregistered*
        value, so it surfaces as an explode error instead of silently tokenising into
        committed source that no teammate's environment can build. Environment mode
        with no committed connection file is a hard error here — there is nothing to
        tokenize against, so every real connection string would otherwise be reported
        as 'unregistered' one-by-one rather than with one clear message."""
        self._require_env("the committed connection reverse map")
        files = self.committed_connection_files()
        if not files:
            sys.exit(
                f"aprx-tools: {self.dir} is an environment-mode project but has no "
                f"{conn.CONNECTIONS_DIR}/*.json to tokenize against — "
                f"run `aprx connections init` or add a connections file"
            )
        return conn.build_reverse_map(files)

    def forward_map(self, env=None, connections_file=None) -> "dict[str, str]":
        """``{key: connection_string}`` for one chosen environment — used to
        **substitute** on pack. Precedence: ``connections_file`` > ``env`` >
        ``local.json`` (see ``connections.resolve_connections_file``). Errors if
        nothing resolves, so pack never emits a Project full of bare tokens."""
        self._require_env("the connection forward map")
        path = conn.resolve_connections_file(self.dir, env, connections_file)
        if path is None:
            sys.exit(
                f"aprx-tools: {self.dir} has no connection values to pack with "
                f"(no --connections, no --env, no {conn.LOCAL_FILE})"
            )
        return conn.load_connections(path)
