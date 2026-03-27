# Quickstart: gphotos-sync with YAML Multi-Profile Config (Playwright)

## Prerequisites

- Python 3.9+
- Google Chrome or Chromium installed (used by Playwright for browser automation)
- One or more Google accounts with Google Photos

> **No Google Cloud Console setup required.** This tool uses browser automation, not the
> Google Photos Library API, so no OAuth client credentials are needed.

---

## 1. Install Dependencies

```bash
pip install pyyaml playwright
playwright install chromium
```

---

## 2. Create the Config File

Create `~/.gphotos-sync/config.yml` (Windows: `C:\Users\YourName\.gphotos-sync\config.yml`):

```yaml
personal:
  destination: C:/Users/YourName/photos/personal
  token_dir: C:/Users/YourName/.gphotos-sync/personal

work:
  destination: C:/Users/YourName/photos/work
  token_dir: C:/Users/YourName/.gphotos-sync/work

default:
  destination: C:/Users/YourName/photos/personal
  token_dir: C:/Users/YourName/.gphotos-sync/personal
  date_offset: -1   # Default: download yesterday's photos
```

> **All paths must be absolute.** Relative paths are rejected with an error.
>
> `token_dir` directories are created automatically if they do not exist.

---

## 3. First Run — Log Into Each Account

On first run per profile, a **visible browser window opens** for you to sign in to Google.
Complete the sign-in normally (including any 2FA prompt). Once signed in to Google Photos,
return to the terminal — the tool detects the successful login and saves your session.

```bash
# First run: personal profile — browser opens for Google login
python -m src.photo_sync --profile personal

# First run: work profile
python -m src.photo_sync --profile work
```

The browser session is saved as `playwright_state.json` in each profile's `token_dir`. **Do not share
or commit this file** — it contains authentication cookies for your Google account.

---

## 4. Daily Sync

After first login, the tool runs headlessly (no visible browser) on all subsequent runs:

```bash
# Sync yesterday's photos for the personal profile (default: date_offset = -1)
python -m src.photo_sync --profile personal

# Sync a specific date
python -m src.photo_sync --profile personal --date 2026-03-24

# Sync all profiles sequentially
python -m src.photo_sync --profile all

# Use the "default" profile (no --profile flag needed)
python -m src.photo_sync
```

---

## 5. Catch-Up Run (Missed Dates)

If a daily run failed, use `--start-date` / `--end-date` to re-download a date range:

```bash
python -m src.photo_sync --profile personal --start-date 2026-03-20 --end-date 2026-03-24
```

Each day in the range is downloaded individually. Existing files are overwritten.

---

## 6. Scheduled Daily Sync

### Windows Task Scheduler

```
Action: Start a program
Program: python
Arguments: -m src.photo_sync --profile all
Start in: C:\path\to\gphotos-sync
```

### Linux/macOS cron

```cron
# Every day at 8am — sync all accounts
0 8 * * * cd /path/to/gphotos-sync && python -m src.photo_sync --profile all >> ~/gphotos-sync.log 2>&1
```

---

## 7. Adding a New Profile

Add a new top-level key to `~/.gphotos-sync/config.yml`:

```yaml
family:
  destination: C:/Users/YourName/photos/family
  token_dir: C:/Users/YourName/.gphotos-sync/family
```

Then run once to log in:

```bash
python -m src.photo_sync --profile family
```

---

## File Layout After Setup

```
~/.gphotos-sync/
├── config.yml
├── gphotos-sync.log              # today's log (auto-created on first run)
├── gphotos-sync.log.2026-03-25  # prior day's log (up to 7 days retained)
├── personal/
│   └── playwright_state.json   # auto-created after first login (do not commit)
└── work/
    └── playwright_state.json

C:/Users/YourName/photos/
├── personal/
│   └── 2026/03/24/
│       └── IMG_0001.jpg
└── work/
    └── 2026/03/24/
        └── IMG_0002.jpg
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Config file not found` | Create `~/.gphotos-sync/config.yml` or pass `--config <path>` |
| `missing required field: destination` | Check both required fields are set in the profile |
| `must be an absolute path` | Change path values to absolute paths |
| `Profile "X" not found. Available profiles: ...` | Fix the `--profile` value or add the profile |
| `No "default" profile found` | Add a `default:` section or use `--profile <name>` |
| Browser window did not open | Ensure `playwright install chromium` has been run |
| Login loop / session not saving | Check `token_dir` is writable; verify `playwright_state.json` was created |
| Session expired message | Expected behaviour — a browser window will re-open for re-login |
| Photos from one date missing after sync | Use `--date YYYY-MM-DD` to re-run just that day |
