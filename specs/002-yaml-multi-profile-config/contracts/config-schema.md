# Config File Schema Contract: gphotos-sync

**Branch**: `002-yaml-multi-profile-config` | **Updated**: 2026-03-25

## File Location

| Resolution | Path |
|---|---|
| Default | `~/.gphotos-sync/config.yml` |
| Override | Value of `--config <path>` CLI flag |

---

## File Format

YAML (`yaml.safe_load()` only). Human-readable, editable without special tooling.
Profile names are **top-level keys** — no `profiles:` wrapper.

### Minimal Profile (required fields only)

```yaml
personal:
  destination: C:/Users/User/photos/personal
  token_dir: C:/Users/User/.gphotos-sync/personal
```

### Full Profile (all fields)

```yaml
personal:
  destination: C:/Users/User/photos/personal
  token_dir: C:/Users/User/.gphotos-sync/personal
  date_offset: -1       # integer; days from today used as default --date (-1 = yesterday)
  verbose: false
```

### Multi-Profile File

```yaml
personal:
  destination: C:/Users/User/photos/personal
  token_dir: C:/Users/User/.gphotos-sync/personal

work:
  destination: C:/Users/User/photos/work
  token_dir: C:/Users/User/.gphotos-sync/work

default:
  destination: C:/Users/User/photos/personal
  token_dir: C:/Users/User/.gphotos-sync/personal
  verbose: true
```

---

## Field Reference

### Required Fields (all profiles)

| Field | YAML Type | Validation | Description |
|---|---|---|---|
| `destination` | string | Absolute path | Local root folder where downloaded photos are saved |
| `token_dir` | string | Absolute path | Directory where `playwright_state.json` is stored |

### Optional Fields

| Field | YAML Type | Default | Description |
|---|---|---|---|
| `date_offset` | int | `-1` | Days from today used as default when `--date` is omitted (e.g., `-1` = yesterday) |
| `verbose` | bool | `false` | Print per-item progress lines |

**Removed fields** (compared to original design): `credentials_path`, `date_from`, `date_to`,
`max_backoff_seconds`, `lookback_pages`, `dry_run`.

---

## Validation Rules

Enforced on startup, before any browser is opened (FR-008).

| Rule | Error message pattern |
|---|---|
| File missing | `ERROR: Config file not found: <path>` |
| File unparseable | `ERROR: Config file parse error in <path>: <yaml error>` |
| File has no profiles | `ERROR: Config file contains no profiles: <path>` |
| Profile missing required field | `ERROR: Profile "<name>" is missing required field: <field>` |
| Path field is relative | `ERROR: Profile "<name>": field "<field>" must be an absolute path, got: <value>` |
| Profile name is "all" | `ERROR: Profile name "all" is reserved and cannot be used` |
| Profile name requested not found | `ERROR: Profile "<name>" not found. Available profiles: <list>` |
| No default profile, no --profile given | `ERROR: No "default" profile found. Available profiles: <list>` |

---

## Profile Name Rules

- Profile names are the top-level YAML keys.
- Names are **case-sensitive** (`Personal` ≠ `personal`).
- Names must be **unique** within the file (YAML enforces this natively).
- The name `all` is **reserved** — using it is a validation error.
- Empty/blank keys are rejected by the YAML parser.

---

## CLI Override Interaction

```
CLI flag (highest) → profile field → built-in default (lowest)
```

- `destination` can be overridden via `--dest` CLI flag.
- `verbose` can be overridden via `-v` CLI flag.
- `token_dir` cannot be overridden via CLI (required; sourced from profile only).
