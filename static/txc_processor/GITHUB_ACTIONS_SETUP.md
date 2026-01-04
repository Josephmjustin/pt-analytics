# TXC Schedule Processing - GitHub Actions Setup

## Overview

This setup uses **GitHub Actions** for heavy TXC processing (7GB RAM) triggered by lightweight HEAD checks from **VM #1** (1GB RAM).

## Architecture

**VM #1 (every 2 hours):**
- HEAD check monthly URL for size change
- HEAD check daily URL for new updates
- If change detected → Trigger GitHub Actions webhook

**GitHub Actions (on-demand):**
- Monthly: ~1 run/month × 120 min = 120 min/month
- Daily: ~31 runs/month × 15 min = 465 min/month
- **Total: ~585 minutes/month** ✓ Within 2,000 free tier limit

## Setup Instructions

### 1. Create GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Name: `TXC Processor Webhook`
4. Scopes: Check **`repo`** (full control)
5. Generate token
6. **SAVE THE TOKEN** - you'll need it for VM and GitHub secrets

### 2. Add GitHub Repository Secrets

Go to: **Your Repo → Settings → Secrets and variables → Actions**

Add these secrets:
- `DB_HOST` = `141.147.106.59`
- `DB_USER` = `pt_api`
- `DB_PASSWORD` = `<your_postgresql_password>`
- `DB_NAME` = `pt_analytics_schedules`

### 3. Push Workflow to GitHub

```bash
cd C:/Users/justi/Work/Personal/pt-analytics

git add .github/workflows/txc-processor.yml
git add static/txc_processor/download_daily.py
git add static/txc_processor/check_and_trigger.sh
git commit -m "Add GitHub Actions TXC processor with webhook triggers"
git push
```

### 4. Setup VM #1 Head Checker

**SSH to VM #1:**

```bash
ssh -i ~/.ssh/oci_pt_analytics ubuntu@141.147.93.150
```

**Upload the trigger script:**

```bash
# From your Windows machine
scp -i C:/Users/justi/.ssh/oci_pt_analytics C:/Users/justi/Work/Personal/pt-analytics/static/txc_processor/check_and_trigger.sh ubuntu@141.147.93.150:~/pt-analytics/static/txc_processor/
```

**Configure the script:**

```bash
# On VM #1
cd ~/pt-analytics/static/txc_processor
nano check_and_trigger.sh

# UPDATE these lines (around line 7-8):
GITHUB_REPO="YOUR_USERNAME/pt-analytics"  # e.g., "justinjj94/pt-analytics"
GITHUB_TOKEN="YOUR_GITHUB_TOKEN"          # The token from Step 1

# Save and exit (Ctrl+X, Y, Enter)

# Make executable
chmod +x check_and_trigger.sh
```

**Create log directory:**

```bash
sudo mkdir -p /var/log/pt-analytics
sudo chown ubuntu:ubuntu /var/log/pt-analytics
```

**Test the script:**

```bash
./check_and_trigger.sh

# Check the log
cat /var/log/pt-analytics/txc_checker.log
```

### 5. Add Cron Job on VM #1

```bash
crontab -e

# Add this line (runs every 2 hours):
0 */2 * * * /home/ubuntu/pt-analytics/static/txc_processor/check_and_trigger.sh

# Save and exit
```

**Verify cron job:**

```bash
crontab -l
```

### 6. Test the Complete Flow

**Option A: Manual GitHub Actions trigger**

Go to: **Your Repo → Actions → TXC Schedule Processor → Run workflow**

Select:
- Branch: main
- Click "Run workflow"

**Option B: Manual webhook trigger from VM**

```bash
# On VM #1
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  "https://api.github.com/repos/YOUR_USERNAME/pt-analytics/dispatches" \
  -d '{"event_type":"monthly-update"}'
```

Check **GitHub → Actions** tab - you should see the workflow running!

## How It Works

### Monthly Update Flow

1. VM checks: `HEAD https://data.bus-data.dft.gov.uk/timetable/download/bulk_archive/NW`
2. If Content-Length changed → Trigger `monthly-update` event
3. GitHub Actions:
   - Downloads ~332MB ZIP to `/tmp/txc_monthly/`
   - Extracts ~12,962 XML files
   - Processes with `create_schedule_efficient.py`
   - **TRUNCATES** `stop_schedule` table
   - Inserts all schedules fresh
4. VM marks month as processed (stops checking until next month)

### Daily Update Flow

1. VM checks: `HEAD https://data.bus-data.dft.gov.uk/timetable/download/change_archive/YYYY-MM-DD/`
2. If HTTP 200 (exists) → Trigger `daily-update` event with date
3. GitHub Actions:
   - Downloads daily ZIP to `/tmp/txc_daily/`
   - Extracts changed XML files
   - Processes with `process_daily_incremental.py`
   - **UPDATES** only affected patterns (no truncation)

## File Locations

**GitHub Actions (temporary, cleaned after run):**
- `/tmp/txc_monthly/` - Monthly downloads
- `/tmp/txc_daily/` - Daily downloads

**VM #1:**
- `/home/ubuntu/pt-analytics/static/txc_processor/tracking/` - Tracking files
- `/var/log/pt-analytics/txc_checker.log` - Check logs

**No files stored permanently - all processing happens in memory!**

## Monitoring

**Check VM logs:**
```bash
tail -f /var/log/pt-analytics/txc_checker.log
```

**Check GitHub Actions:**
- Go to: **Your Repo → Actions**
- Click on workflow run
- View logs for each step

**Check cron job:**
```bash
crontab -l
grep CRON /var/log/syslog
```

## Troubleshooting

**GitHub Actions not triggering:**
- Check token has `repo` scope
- Verify `GITHUB_REPO` and `GITHUB_TOKEN` in `check_and_trigger.sh`
- Check VM log for HTTP response codes

**Database connection fails:**
- Verify GitHub secrets are set correctly
- Test connection from GitHub Actions (add debug step)

**Processing takes too long:**
- Monthly: Should complete in ~2 hours
- Daily: Should complete in ~15 minutes
- Check GitHub Actions logs for bottlenecks

## Cost Analysis

**GitHub Actions Free Tier:**
- 2,000 minutes/month
- 500MB storage

**Expected Usage:**
- Monthly: 1 run × 120 min = 120 min
- Daily: 31 runs × 15 min = 465 min
- **Total: 585 min/month (29% of quota)**

**Well within free tier! ✓**
