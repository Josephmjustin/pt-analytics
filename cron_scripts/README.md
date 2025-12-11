# PT Analytics - Cron Migration

## Migration from Prefect to Cron

This directory contains scripts to replace Prefect with system cron for job scheduling.

### Benefits
- **Zero memory overhead** (no Prefect agent/server)
- **More reliable** on low-memory VMs
- **Simpler** - uses native Linux scheduler
- **Same functionality** - runs identical logic

### Files

```
cron_scripts/
├── run_ingestion.py      # Standalone ingestion script
├── run_analysis.py       # Standalone analysis script
├── install_cron.sh       # Install cron jobs
├── uninstall_cron.sh     # Remove cron jobs
├── crontab.txt           # Template crontab
└── README.md             # This file
```

## Installation (On Oracle VM)

### 1. Upload to VM

```bash
# From local machine
cd ~/pt-analytics
scp -r cron_scripts ubuntu@your-vm-ip:~/pt-analytics/
```

### 2. Install on VM

```bash
# SSH into VM
ssh ubuntu@your-vm-ip

# Navigate to project
cd ~/pt-analytics/cron_scripts

# Make installer executable
chmod +x install_cron.sh

# Run installer
./install_cron.sh
```

The installer will:
1. Create logs directory
2. Make scripts executable
3. Test both scripts
4. Generate crontab with correct paths
5. Backup existing crontab
6. Install new crontab

### 3. Verify

```bash
# Check crontab installed
crontab -l

# Monitor logs
tail -f ~/pt-analytics/logs/ingestion.log
tail -f ~/pt-analytics/logs/analysis.log

# Check if running
ps aux | grep run_ingestion
ps aux | grep run_analysis
```

## Schedule

- **Ingestion**: Every 10 seconds (6 times per minute)
- **Analysis**: Every 10 minutes
- **Log rotation**: Daily at 2 AM (truncates logs > 50MB)

## Uninstallation

```bash
cd ~/pt-analytics/cron_scripts
chmod +x uninstall_cron.sh
./uninstall_cron.sh
```

## Stop Prefect (After Migration)

```bash
# Find Prefect process
ps aux | grep prefect

# Kill it
kill <PID>

# Or if using systemd service
sudo systemctl stop prefect
sudo systemctl disable prefect
```

## Troubleshooting

### Scripts not running

```bash
# Check cron service
sudo systemctl status cron

# Check logs for errors
tail -50 ~/pt-analytics/logs/ingestion.log
tail -50 ~/pt-analytics/logs/analysis.log
```

### Python import errors

Make sure environment variables are loaded:
```bash
# Add to crontab if needed
PYTHONPATH=/home/ubuntu/pt-analytics
```

### Memory issues persist

```bash
# Check memory usage
free -h
htop

# Reduce ingestion frequency (edit crontab)
crontab -e
# Change to every 30s: */30 * * * * ...
```

## Logs

Logs are stored in `~/pt-analytics/logs/`:
- `ingestion.log` - Data ingestion output
- `analysis.log` - Analysis pipeline output
- `crontab.backup.*` - Crontab backups

Logs auto-rotate daily (keep only last 50MB).

## Comparison

| Feature | Prefect | Cron |
|---------|---------|------|
| Memory | ~50-100MB | ~0MB |
| Setup | Agent + Server | Native |
| UI | Web dashboard | Logs |
| Reliability | Cloud dependent | Local |
| Scheduling | Python code | Crontab |
| Monitoring | Built-in | Manual |

## Next Steps

After successful migration:
1. Monitor for 24 hours
2. Verify data ingestion continues
3. Check analysis runs correctly
4. Remove Prefect from requirements.txt
5. Uninstall Prefect: `pip uninstall prefect`
