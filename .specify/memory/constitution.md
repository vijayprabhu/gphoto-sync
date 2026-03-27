<!--
SYNC IMPACT REPORT
==================
Version change: [blank template] → 1.0.0
Type: Initial ratification (all content new — no prior principles to diff)

Principles added:
  I.   Single-Responsibility Modules
  II.  Security-First Credential Handling
  III. Idempotent Sync Operations
  IV.  CLI Contract Compliance
  V.   Simplicity and YAGNI

Sections added:
  - Core Principles (5 principles)
  - Security Constraints
  - Development Workflow
  - Governance

Templates reviewed:
  ✅ .specify/templates/plan-template.md   — Constitution Check placeholder works as-is; no update needed
  ✅ .specify/templates/spec-template.md   — No constitution references; no update needed
  ✅ .specify/templates/tasks-template.md  — No constitution references; no update needed
  ✅ .specify/templates/agent-file-template.md — No constitution references; no update needed
  ✅ CLAUDE.md                             — No constitution references; no update needed

Follow-up TODOs:
  - None. All fields resolved from repo context.
-->

# gphotos-sync Constitution

## Core Principles

### I. Single-Responsibility Modules

Each Python module in `src/` MUST have exactly one clearly bounded concern.
The mandated module-to-concern mapping is:

- `auth.py` — OAuth2 credential loading, refresh, browser flow, and token persistence
- `client.py` — Google Photos Library API wrapper (search, list, pagination, retry)
- `config.py` — CLI argument parsing and `SyncConfig` dataclass construction
- `config_loader.py` — YAML config file loading, profile validation, and profile selection
- `downloader.py` — Sync state persistence, per-item download logic, and run orchestration
- `photo_sync.py` — CLI entry point: argument dispatch, single/multi-profile orchestration,
  output formatting

New concerns MUST be introduced as new modules, not appended to existing ones.
Existing modules MUST NOT acquire responsibilities outside their stated concern.

### II. Security-First Credential Handling

Sensitive files MUST NEVER be committed to version control. The following filenames are
in `.gitignore` and MUST remain there at all times: `credentials.json`, `token.json`,
`synced_ids.json`.

Token persistence MUST use `Credentials.to_json()` / `Credentials.from_authorized_user_info()`
(plain JSON). The use of `pickle` for any credential or state serialization is prohibited.

YAML config loading MUST use `yaml.safe_load()`. Calling `yaml.load()` without an explicit
safe Loader is prohibited.

All path fields in the YAML config (`credentials_path`, `destination`, `token_dir`) MUST be
absolute paths. Relative paths MUST be rejected at config validation time with an actionable
error message naming the field and the offending value.

### III. Idempotent Sync Operations

Re-running the sync tool with the same arguments MUST NOT re-download already-synced items.
Two skip conditions MUST be enforced per item, in order:

1. Item `id` is present in `synced_ids.json` (persisted state check).
2. Filename already exists at `<destination>/YYYY/MM/DD/<filename>` (disk existence check).

`synced_ids.json` MUST be written to disk after each individual successful download (not
batched at end of run), so that a mid-run crash preserves all progress made so far.

The upload-date proxy approach — combining `mediaItems.search` (capture-date filter) with
`mediaItems.list` (recent items) and local `synced_ids.json` state — is the canonical
mechanism for covering both capture-date and upload-date scenarios. The Google Photos API
exposes no `uploadTime` field; this pattern is the established substitute.

### IV. CLI Contract Compliance

The tool MUST emit structured output as defined in the `contracts/cli-contract.md` artifact
for each feature. The routing rules are non-negotiable:

- **stdout**: run summary and per-item verbose lines (when `--verbose` is active)
- **stderr**: all errors, warnings, validation failures, and per-item download failures

Exit codes MUST be:

| Code | Meaning |
|------|---------|
| `0` | Success — run completed (per-item failures appear in summary but do not raise exit code) |
| `1` | Fatal error — auth failure, invalid config, destination not writable, or any profile failure in `--profile all` |
| `2` | Invalid arguments — handled automatically by `argparse` |

Config validation (required fields, absolute paths, reserved profile names) MUST complete
before any network activity (Google API calls or OAuth browser flow). This rule is a hard gate:
no network call may precede a successful validation pass.

### V. Simplicity and YAGNI

The minimum supported Python version is 3.9+. Features requiring 3.10 or later
(e.g., `match` statements, `ExceptionGroup`) MUST NOT be used unless the minimum version
is explicitly raised by a recorded decision.

All filesystem path construction MUST use `pathlib.Path` division (`/` operator), never
string concatenation or `os.path.join`. This guarantees platform-appropriate separators
(`\` on Windows, `/` on Unix/macOS).

`--profile all` MUST run profiles sequentially. Concurrent execution is out of scope and
MUST NOT be anticipated with premature abstractions (e.g., `asyncio`, `threading`,
`multiprocessing`).

No third-party dependency may be added to `requirements.txt` without a recorded research
decision (`research.md` Decision entry) that documents the rationale and alternatives
considered.

Shell commands via `os.system()` or `subprocess` with untrusted input are prohibited.
HTTP downloads MUST use `requests.get()` directly.

## Security Constraints

These constraints extend Principle II and apply to the entire codebase:

- OAuth client secrets (`credentials.json`) are user-provided. The tool MUST NOT modify,
  move, or delete them.
- The YAML config file stores paths to credential files, never credential content itself.
- OAuth tokens (`token.json`) and sync state (`synced_ids.json`) are tool-managed and MUST
  be stored in each profile's `token_dir`, not in the repository.
- The `.gitignore` MUST exclude `credentials.json`, `token.json`, and `synced_ids.json`
  with patterns that match these filenames at any directory depth.

## Development Workflow

Features follow the speckit workflow in strict order:

1. `/speckit.specify` — produce `spec.md` with user stories, acceptance criteria, edge cases,
   and measurable success criteria.
2. `/speckit.clarify` — resolve ambiguities in the spec (up to 5 targeted questions).
3. `/speckit.plan` — produce `research.md` (decisions), `data-model.md`, `contracts/`,
   `quickstart.md`, and `plan.md`.
4. `/speckit.tasks` — produce `tasks.md` with phase-organized, dependency-ordered tasks.
5. `/speckit.implement` — execute tasks in order; mark each `[x]` on completion.

Unit tests live in `tests/unit/`. Integration tests live in `tests/integration/`.
All tests MUST pass (`python -m pytest`) before a feature is considered complete.

Tests MUST verify observable behavior, not implementation internals. Mocking is acceptable
for external I/O (network calls via `requests.get`, Google API responses) but MUST NOT mock
the module under test itself.

## Governance

This constitution supersedes all other project conventions when they conflict.
Amendments require:

1. A clear written rationale for the change.
2. A version bump following the semantic versioning policy below.
3. Propagation of any impacted rules to dependent templates
   (`plan-template.md`, `spec-template.md`, `tasks-template.md`) and a Sync Impact Report
   embedded as an HTML comment at the top of the updated constitution file.

**Versioning policy**:

| Bump | Trigger |
|------|---------|
| MAJOR | Backward-incompatible removal or redefinition of an existing principle |
| MINOR | New principle or new section added; material expansion of existing guidance |
| PATCH | Wording clarification, typo fix, non-semantic refinement |

All plan reviews (`/speckit.plan`) MUST include a Constitution Check section confirming no
gates are violated. If the constitution has not yet been ratified (still contains placeholder
tokens), the check MUST note this and proceed without gates.

Complexity beyond the minimum needed for the current task MUST be explicitly justified in
`plan.md` under a Complexity Tracking section.

**Version**: 1.0.0 | **Ratified**: 2026-03-22 | **Last Amended**: 2026-03-22
