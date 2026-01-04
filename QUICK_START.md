# Quick Start Guide - GitHub Actions TXC Processing

## ⚡ 5-Minute Setup

### Step 1: Create GitHub Personal Access Token (2 min)

1. **Go to:** https://github.com/settings/tokens
2. **Click:** "Generate new token (classic)"
3. **Settings:**
   - Note: `TXC Processor Webhook`
   - Expiration: `No expiration` (or 1 year)
   - Scopes: ✅ **repo** (check the entire repo section)
4. **Generate token**
5. **COPY THE TOKEN** (you won't see it again!)
   - Save it temporarily - you'll use it in Step 3

---

### Step 2: Add GitHub Repository Secrets (2 min)

1. **Go to:** https://github.com/Josephmjustin/pt-analytics/settings/secrets/actions
2. **Click:** "New repository secret" for each:

| Name | Value |
|------|-------|
| `DB_HOST` | `141.147.106.59` |
| `DB_USER` | `pt_api` |
| `DB_PASSWORD` | Your PostgreSQL password for VM #2 |
| `DB_NAME` | `pt_analytics_schedules` |

---

### Step 3: Push to GitHub (1 min)

```bash
cd C:/Users/justi/Work/Personal/pt-analytics

# Check what's new
git status

# Add all new files
git add .github/workflows/txc-processor.yml
git add static/txc_processor/check_and_trigger.sh
git add static/txc_processor/download_daily.py
git add static/txc_processor/GITHUB_ACTIONS_SETUP.md
git add IMPLEMENTATION_SUMMARY.md

# Commit
git commit -m "Add GitHub Actions TXC processor with webhook triggers"

# Push
git push
```

---

### Step 4: Setup VM #1 (5 min)

**A. Upload the trigger script:**

```bash
# From Windows machine
scp -i C:/Users/justi/.ssh/oci_pt_analytics C:/Users/justi/Work/Personal/pt-analytics/static/txc_processor/check_and_trigger.sh ubuntu@141.147.93.150:~/pt-analytics/static/txc_processor/
```

**B. Configure the script:**

```bash
# SSH to VM
ssh -i C:/Users/justi/.ssh/oci_pt_analytics ubuntu@141.147.93.150

# Edit the script
cd ~/pt-analytics/static/txc_processor
nano check_and_trigger.sh

# Find this line (around line 8):
GITHUB_TOKEN="YOUR_GITHUB_TOKEN"

# Replace YOUR_GITHUB_TOKEN with your actual token from Step 1
# Example: GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Save and exit: Ctrl+X, then Y, then Enter
```

**C. Make executable and create log directory:**

```bash
chmod +x check_and_trigger.sh
sudo mkdir -p /var/log/pt-analytics
sudo chown ubuntu:ubuntu /var/log/pt-analytics
```

---

### Step 5: Test the Setup (2 min)

**Test the head checker:**

```bash
# On VM #1
cd ~/pt-analytics/static/txc_processor
./check_and_trigger.sh

# Check the log
cat /var/log/pt-analytics/txc_checker.log
```

**You should see:**
```
========================================
2026-01-04 XX:XX:XX: TXC Update Check Starting
========================================
2026-01-04 XX:XX:XX: Checking monthly bulk archive...
2026-01-04 XX:XX:XX: Monthly archive size: 348133038 bytes
2026-01-04 XX:XX:XX: First check - saving baseline size
2026-01-04 XX:XX:XX: Checking daily update for 2026-01-04...
2026-01-04 XX:XX:XX: No daily update yet for 2026-01-04 (HTTP 404)
2026-01-04 XX:XX:XX: Check complete
========================================
```

**Test GitHub Actions trigger (optional):**

```bash
# Manual trigger to verify webhook works
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  "https://api.github.com/repos/Josephmjustin/pt-analytics/dispatches" \
  -d '{"event_type":"monthly-update"}'

# Then check: https://github.com/Josephmjustin/pt-analytics/actions
```

---

### Step 6: Add Cron Job (1 min)

```bash
# On VM #1
crontab -e

# Add this line at the end:
0 */2 * * * /home/ubuntu/pt-analytics/static/txc_processor/check_and_trigger.sh

# Save and exit: Ctrl+X, then Y, then Enter

# Verify it's added:
crontab -l
```

---

## ✅ Setup Complete!

**What happens now:**

1. **Every 2 hours:** VM checks BODS for updates (lightweight HEAD requests)
2. **When update detected:** VM triggers GitHub Actions webhook
3. **GitHub Actions:** Downloads & processes TXC files (uses 7GB RAM)
4. **Database updated:** VM #2 PostgreSQL gets fresh schedules

**Monitor:**
- VM logs: `tail -f /var/log/pt-analytics/txc_checker.log`
- GitHub Actions: https://github.com/Josephmjustin/pt-analytics/actions

**Expected GitHub Actions usage:**
- Monthly: ~1 run/month × 120 min = **120 min/month**
- Daily: ~31 runs/month × 15 min = **465 min/month**
- **Total: 585 min/month** (29% of 2,000 free tier)

---

## Quick Reference Commands

**Check VM logs:**
```bash
tail -20 /var/log/pt-analytics/txc_checker.log
```

**Force monthly update check:**
```bash
cd ~/pt-analytics/static/txc_processor
rm -f tracking/monthly_size.txt tracking/processed_month.txt
./check_and_trigger.sh
```

**View cron jobs:**
```bash
crontab -l
```

**GitHub Actions page:**
https://github.com/Josephmjustin/pt-analytics/actions
