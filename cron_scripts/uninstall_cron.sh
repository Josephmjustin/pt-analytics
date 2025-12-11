#!/bin/bash
# Uninstall PT Analytics cron jobs

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
LOGS_DIR="$PROJECT_DIR/logs"

echo -e "${GREEN}PT Analytics - Cron Uninstallation${NC}"
echo "====================================="
echo ""

echo "Current crontab:"
crontab -l 2>/dev/null || echo "(no crontab)"
echo ""

read -p "Remove PT Analytics cron jobs? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup
    crontab -l > "$LOGS_DIR/crontab.backup.$(date +%s)" 2>/dev/null || true
    
    # Remove PT Analytics entries
    crontab -l 2>/dev/null | grep -v "PT Analytics" | grep -v "run_ingestion.py" | grep -v "run_analysis.py" | crontab -
    
    echo -e "${GREEN}✓ PT Analytics cron jobs removed${NC}"
    echo ""
    echo "Remaining crontab:"
    crontab -l 2>/dev/null || echo "(empty)"
else
    echo -e "${YELLOW}Uninstallation cancelled${NC}"
fi
