# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (breaking)

- **A project's mode is now declared, not detected.** The mode (`simple` or `env`) is
  read from a `"mode"` field in a committed `aprx.json` and is the single source of
  truth. The previous heuristic — inferring environment mode from the mere presence of
  an `aprx.json`, a `connections/` directory, or a `local.json` — has been removed.
  Resolution is strict: a project with no `aprx.json`, or one whose `aprx.json` has no
  `mode`, is a hard error that directs you to run `aprx install`. There is no
  back-compat inference.

  **Migration (one-time, per project):** run `aprx install` from the project's
  directory to record the mode (or `aprx install --mode simple|env` to set it without
  a prompt), then commit the resulting `aprx.json`. See
  [Upgrading an existing repository](README.md#upgrading-an-existing-repository).

### Added

- `aprx install` records the project mode in `aprx.json`: it prompts on first run,
  accepts `--mode simple|env` to bypass the prompt, defaults to `simple` (with a loud
  warning) in a non-interactive shell with no existing config, and honours an existing
  declaration without prompting — refusing a conflicting `--mode` rather than silently
  overwriting a shared team decision.
- `aprx connections init` records `"mode": "env"` in `aprx.json` as it scaffolds the
  connection files.
