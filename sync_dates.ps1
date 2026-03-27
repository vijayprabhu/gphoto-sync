$start = [datetime]"2025-05-06"
$end   = [datetime]"2026-03-26"

for ($d = $start; $d -le $end; $d = $d.AddDays(1)) {
    $date = $d.ToString("yyyy-MM-dd")
    Write-Host "=== Syncing $date ===" -ForegroundColor Cyan
    python -m src.photo_sync --profile vijayprabhu.venkataraman --date $date
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Command failed for $date (exit code $LASTEXITCODE). Continuing..."
    }
}

Write-Host "Done." -ForegroundColor Green
