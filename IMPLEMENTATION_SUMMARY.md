# GitHub Actions TXC Processing - Implementation Summary

## Files Created

### 1. GitHub Workflow
**Location:** `.github/workflows/txc-processor.yml`
- Triggered by webhook events: `monthly-update` and `daily-update`
- Uses 7GB RAM on GitHub Actions runners
- Processes files in `/tmp/` (temporary, auto-cleaned)
- Connects to VM #2 PostgreSQL using GitHub secrets

### 2. VM Head Checker Script
**Location:** `static/txc_processor/check_and_trigger.sh`
- Runs every 2 hours on VM #1
- Checks monthly archive HEAD for size changes
- Checks daily updates for new folders
- Triggers GitHub Actions via webhook
- Lightweight (~50MB RAM usage)

### 3. Daily Download Script
**Location:** `static/txc_processor/download_daily.py`
- Downloads daily TXC updates from BODS
- Stores in `/tmp/txc_daily/` on GitHub Actions
- Extracts nested operator ZIPs

### 4. Updated Processing Scripts
**Modified:**
- `download_txc.py` - Uses `/tmp/txc_monthly/` on GitHub Actions
- `create_schedule_efficient.py` - Uses env vars for DB connection
- `process_daily_incremental.py` - Uses env vars for DB connection

All scripts now detect GitHub Actions environment and adjust paths automatically.

### 5. Setup Documentation
**Location:** `static/txc_processor/GITHUB_ACTIONS_SETUP.md`
- Complete setup instructions
- Troubleshooting guide
- Cost analysis

## Next Steps

### 1. Get Your GitHub Token
1. Go to: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select `repo` scope
4. Copy the token

### 2. Configure GitHub Secrets
Add these to your repository secrets:
- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

### 3. Update VM Script
Edit `check_and_trigger.sh` and set:
- `GITHUB_REPO` (your username/repo)
- `GITHUB_TOKEN` (from step 1)

### 4. Push to GitHub
```bash
git add .
git commit -m "Add GitHub Actions TXC processor"
git push
```

### 5. Deploy to VM
```bash
# Upload script
scp check_and_trigger.sh ubuntu@141.147.93.150:~/pt-analytics/static/txc_processor/

# Add cron job
# On VM: crontab -e
# Add: 0 */2 * * * /home/ubuntu/pt-analytics/static/txc_processor/check_and_trigger.sh
```

## What's Your GitHub Username?

I need it to complete the setup instructions!
