# Quickstart: gphotos-sync

## Prerequisites

- Python 3.9+
- A Google account with Google Photos
- A Google Cloud project with the Photos Library API enabled and OAuth 2.0 credentials downloaded as `credentials.json`

## 1. Install Dependencies

```bash
pip install google-api-python-client google-auth google-auth-oauthlib google-api-core requests
```

## 2. Set Up Google Cloud Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials.
2. Create an **OAuth 2.0 Client ID** (Desktop app type).
3. Download the JSON file and rename it `credentials.json`.
4. Place it in your config directory (default: `~/.gphotos-sync/`):

```bash
mkdir -p ~/.gphotos-sync
cp ~/Downloads/credentials.json ~/.gphotos-sync/
```

## 3. First Run (Authorization)

On first run, a browser window opens for Google account authorization. After approval, `token.json` is saved to the config directory for future runs.

```bash
python -m src.photo_sync --dest ~/photos
```

Follow the browser prompt to authorize. Once complete, the sync begins.

## 4. Subsequent Runs

```bash
# Sync yesterday and today (default)
python -m src.photo_sync --dest ~/photos

# Sync a specific date range
python -m src.photo_sync --dest ~/photos --date-from 2026-03-01 --date-to 2026-03-07

# Dry run — see what would be downloaded
python -m src.photo_sync --dest ~/photos --dry-run

# Verbose output
python -m src.photo_sync --dest ~/photos --verbose
```

## 5. Multiple Google Accounts

```bash
# Set up a second account
mkdir -p ~/.gphotos-sync/work
cp ~/Downloads/work-credentials.json ~/.gphotos-sync/work/credentials.json

# Sync each account separately
python -m src.photo_sync --dest ~/photos/personal --config-dir ~/.gphotos-sync/
python -m src.photo_sync --dest ~/photos/work --config-dir ~/.gphotos-sync/work/
```

## 6. Scheduled Daily Sync (cron example)

```cron
# Every day at 8am — sync yesterday's and today's photos
0 8 * * * /usr/bin/python3 -m src.photo_sync --dest /mnt/photos >> /var/log/gphotos-sync.log 2>&1
```

## File Layout After Sync

Photos are organized into a `YYYY/MM/DD` hierarchy using the photo's capture date:

```
~/photos/
└── 2026/
    └── 03/
        ├── 21/
        │   ├── IMG_0001.jpg
        │   └── IMG_0002.jpg
        └── 22/
            ├── IMG_0003.jpg
            └── VID_0001.mp4
```

The folder separator is platform-appropriate (`\` on Windows, `/` on Unix/macOS).

## Troubleshooting

| Problem | Solution |
|---|---|
| `credentials.json not found` | Ensure `credentials.json` is in `--config-dir` |
| Browser auth loop repeats | Delete `token.json` from config dir and re-authorize |
| Photos Library API not enabled | Enable it in Google Cloud Console → APIs & Services |
| `destination not writable` | Check folder permissions or specify a different `--dest` |
| HTTP 429 rate limit | Tool retries automatically; increase `--max-backoff` if needed |
