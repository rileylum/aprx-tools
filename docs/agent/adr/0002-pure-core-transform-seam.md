# Connection substitution is an injected transform, not baked into the core

## Status

accepted

## Context & decision

`explode` and `pack` are the version-control core. They no longer know what a connection
is: each accepts a `transform` (default `IDENTITY`) and applies it to every parsed JSON
entry. The transform is two-phase — `apply(parsed)` mutates and accumulates problems per
entry, and `raise_if_problems()` fires once after all entries are computed but before any
output is written. This preserves the core's existing guarantee (compute everything,
validate, *then* touch the filesystem) and reports every problem at once, while the
connection-specific error wording lives behind the seam.

Environment mode supplies a `Substitution` adapter at that seam
(`Substitution.for_explode` → value-to-token, `Substitution.for_pack` → token-to-value);
simple mode supplies `IDENTITY`, a no-op. The two adapters are what justify the seam.

A single `ProjectConfig` object, loaded from `aprx.json`, is the one home for the
resolution ritual (mode, fields, token, connection-file discovery, map building). Both
`Substitution` factories are built from a `ProjectConfig`, and the read-only callers —
`verify`'s token scan and `bootstrap`'s value collection — go through the same object, so
the assembly sequence is no longer copy-pasted across four callers.

## Considered options

- **Core returns problems to the caller** — rejected: pushes connection-specific error
  wording back into the composition root and forces the core to inspect the problem set, so
  it isn't really ignorant of connections.
- **Per-field visitor callback** — rejected: moves the JSON tree-walk into the core,
  spreading connection logic thin and making the core *shallower*.
- **Environment layer wraps explode/pack** — rejected: the core owns the zip/format I/O;
  re-exposing parsed entries to an outer wrapper is more awkward than injecting inward.

## Consequences

- The core is testable with zero connection setup (`IDENTITY`); `Substitution` is testable
  by building a `ProjectConfig` and asserting `apply`/`raise_if_problems`.
- `explode.py`/`pack.py` drop their `import connections` and their plain-vs-`_subst` JSON
  helper forks.
- The four near-identical field-walks in the connections engine
  (`tokenize`/`substitute`/`scan`/`collect`) can now share one internal traversal, since
  they all sit behind `ProjectConfig`/`Substitution`.
