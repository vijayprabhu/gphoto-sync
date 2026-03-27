# gphotos-sync

Download photos from Google Photos into a local `YYYY/MM/DD` folder hierarchy.
Supports multiple Google accounts via named profiles in a single YAML config file.

> **No Google Cloud Console setup required.** This tool uses browser automation
> (Playwright/Chromium), not the Google Photos API, so no OAuth client credentials
> or API keys are needed.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Installation](#2-installation)
3. [Configure Profiles](#3-configure-profiles)
4. [Credential Setup (First Login)](#4-credential-setup-first-login)
5. [Running a Sync](#5-running-a-sync)
6. [CLI Reference](#6-cli-reference)
7. [Scheduled Automation](#7-scheduled-automation)
8. [File Layout](#8-file-layout)
9. [Logging](#9-logging)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Requirements

- Python 3.9 or later
- Internet access to reach `photos.google.com`
- One or more Google accounts with Google Photos

---

## 2. Installation

```bash
# Clone the repo
git clone <repo-url>
cd gphotos-sync

# Install Python dependencies
pip install -r requirements.txt

# Install the Chromium browser used by Playwright
playwright install chromium
```

---

## 3. Configure Profiles

The config file lives at `~/.gphotos-sync/config.yml` by default.
Create the directory and file if they do not exist:

```bash
mkdir -p ~/.gphotos-sync
```

**Linux / macOS** — `~/.gphotos-sync/config.yml`:

```yaml
personal:
  token_dir: /home/alice/.gphotos-sync/sessions/personal   # session storage
  destination: /home/alice/Photos/personal                  # where photos are saved

work:
  token_dir: /home/alice/.gphotos-sync/sessions/work
  destination: /home/alice/Photos/work
  date_offset: -2    # optional: pull 2 days back instead of 1
  verbose: true      # optional: print per-photo progress
```

**Windows** — `C:\Users\Alice\.gphotos-sync\config.yml`:

```yaml
personal:
  token_dir: C:\Users\Alice\.gphotos-sync\sessions\personal
  destination: C:\Users\Alice\Pictures\personal

work:
  token_dir: C:\Users\Alice\.gphotos-sync\sessions\work
  destination: C:\Users\Alice\Pictures\work
```

A ready-to-edit sample file is available at [`samples/config.yml`](samples/config.yml).

### Config fields

| Field | Required | Description |
|---|---|---|
| `token_dir` | **Yes** | Absolute path. Playwright session file (`playwright_state.json`) is stored here. Created automatically if it does not exist. |
| `destination` | **Yes** | Absolute path. Root folder for downloaded photos, organised as `YYYY/MM/DD/`. Created automatically. |
| `date_offset` | No | Integer. How many days back to sync when no `--date` flag is given. `-1` = yesterday (default). |
| `verbose` | No | `true`/`false`. Print per-photo filenames during sync. Default: `false`. |

> **All paths must be absolute.** Relative paths are rejected at startup before any browser is opened.

---

## 4. Credential Setup (First Login)

gphotos-sync authenticates by letting you log in to Google in a real browser window.
**No API keys, OAuth clients, or service accounts are needed.**

Run the tool once per profile. A browser window will open automatically:

```bash
# Log in to your personal account
python -m src.photo_sync --profile personal

# Log in to your work account (separate session)
python -m src.photo_sync --profile work
```

What happens:

1. Chromium opens and navigates to `photos.google.com`.
2. Complete the Google sign-in normally — including any 2-factor prompt.
3. Once you reach Google Photos, return to the terminal.
4. The tool detects the successful login, saves the session to `playwright_state.json`
   in the profile's `token_dir`, and begins the photo sync.

**On every subsequent run** the saved session is reused and no browser window appears.

### Security notes

- `playwright_state.json` contains authentication cookies for your Google account.
  **Do not share, copy, or commit it.**
- It is already listed in `.gitignore`.
- If your session expires, the browser window will reopen automatically for re-login.
- Each profile stores its session in its own `token_dir`, keeping accounts fully isolated.

---

## 5. Running a Sync

### Sync yesterday's photos (default)

```bash
python -m src.photo_sync --profile personal
```

### Sync a specific date

```bash
python -m src.photo_sync --profile personal --date 2026-03-24
```

### Sync a date range (catch-up after missed days)

```bash
python -m src.photo_sync --profile personal --start-date 2026-03-20 --end-date 2026-03-24
```

### Sync all profiles sequentially

```bash
python -m src.photo_sync --profile all
```

Profiles are run one after the other. A failure in one profile is logged and does not
stop the remaining profiles. The final exit code is `1` if any profile failed.

### Use the "default" profile (no flag needed)

Add a profile named `default` in `config.yml`, then run with no `--profile` flag:

```bash
python -m src.photo_sync
```

---

## 6. CLI Reference

```
python -m src.photo_sync [--config PATH] [--profile NAME|all] [OPTIONS]
```

| Flag | Short | Default | Description |
|---|---|---|---|
| `--config PATH` | | `~/.gphotos-sync/config.yml` | Path to the YAML config file |
| `--profile NAME` | `-p` | `default` | Profile to sync, or `all` to run every profile |
| `--dest PATH` | `-d` | *(from profile)* | Override the destination folder for this run only |
| `--date YYYY-MM-DD` | | *(from `date_offset`)* | Sync a single specific date |
| `--start-date YYYY-MM-DD` | | | Range start (inclusive); must be paired with `--end-date` |
| `--end-date YYYY-MM-DD` | | | Range end (inclusive); must be paired with `--start-date` |
| `--verbose` | `-v` | `false` | Print per-photo filenames in addition to the run summary |

**Exit codes:** `0` = success, `1` = fatal error, `2` = invalid arguments.
**stdout:** run summary and verbose photo lines.
**stderr:** all errors, validation failures, and per-item failures.

---

## 7. Scheduled Automation

After the first login, subsequent runs are fully headless and suitable for automation.

### Linux / macOS — cron

```cron
# Every day at 8:00 AM — sync all profiles
0 8 * * * cd /path/to/gphotos-sync && python -m src.photo_sync --profile all >> ~/gphotos-sync.log 2>&1
```

Edit your crontab with `crontab -e` and paste the line above, adjusting the path.

### Windows — Task Scheduler

1. Open **Task Scheduler** → **Create Basic Task**.
2. Set the trigger to **Daily** at your preferred time.
3. Action: **Start a program**
   - Program: `python`
   - Arguments: `-m src.photo_sync --profile all`
   - Start in: `C:\path\to\gphotos-sync`

---

## 8. File Layout

```
~/.gphotos-sync/
├── config.yml                          # all profiles
├── gphotos-sync.log                    # today's log file (auto-created)
├── gphotos-sync.log.2026-03-25         # prior day's log (up to 7 days retained)
├── sessions/
│   ├── personal/
│   │   └── playwright_state.json       # browser session — do not commit
│   └── work/
│       └── playwright_state.json

/your/destination/
└── 2026/
    └── 03/
        └── 24/
            ├── IMG_0001.jpg
            └── IMG_0002.jpg
```

Photos from each day are placed in `YYYY/MM/DD/` under the profile's `destination`.
The folder structure is created automatically.

---

## 9. Logging

Every run writes structured log output to two places simultaneously:

| Destination | Content |
|---|---|
| `~/.gphotos-sync/gphotos-sync.log` | All levels — DEBUG (with `--verbose`), INFO, WARNING, ERROR |
| stdout | INFO run summaries only |
| stderr | WARNING and ERROR only |

**Log rotation**: one file per day, previous 6 days retained automatically. Files older than 7 days are deleted.

**Redaction**: `token_dir` paths and `playwright_state.json` file paths are replaced with `<token_dir>` and `<session_file>` in all log output so credentials locations are never written to disk in plain text.

---

## 10. Troubleshooting

| Problem | Solution |
|---|---|
| `Config file not found` | Create `~/.gphotos-sync/config.yml` or pass `--config <path>` |
| `missing required field: destination` | Ensure both `destination` and `token_dir` are set in the profile |
| `must be an absolute path` | Change all path values to absolute paths — relative paths are not supported |
| `Profile "X" not found. Available profiles: …` | Fix the `--profile` value or add the missing profile to `config.yml` |
| `No "default" profile found` | Add a `default:` section to `config.yml` or always pass `--profile <name>` |
| Browser window did not open | Run `playwright install chromium` and retry |
| Login loop / session not saving | Check that `token_dir` is writable; verify `playwright_state.json` was created after login |
| Session expired | Expected — a browser window will reopen automatically for re-login |
| Photos missing after sync | Use `--date YYYY-MM-DD` to re-run the specific day |
| `--start-date and --end-date must be used together` | Both flags are required when using a date range |
| Log file not created | Check that `~/.gphotos-sync/` is writable; a warning is printed to stderr and the tool continues without the log file |

---

## Running Tests

```bash
python -m pytest
```
