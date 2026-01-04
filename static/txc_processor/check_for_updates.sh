#!/bin/bash
# Unified update checker - checks BOTH daily and monthly updates
# Runs every 2 hours

BASE_DIR="/home/ubuntu/pt-analytics/txc_processor"
LOG_FILE="/var/log/pt-analytics/schedule_check.log"
PROCESSED_DATES_FILE="$BASE_DIR/processed_daily_dates.txt"
LAST_MONTHLY_CHECK_FILE="$BASE_DIR/last_monthly_update.txt"

TODAY=$(date +%Y-%m-%d)

echo "========================================" >> $LOG_FILE
echo "$(date): Checking for schedule updates" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

# ============================================
# 1. CHECK DAILY UPDATES
# ============================================
echo "$(date): Checking daily update for $TODAY..." >> $LOG_FILE

if grep -q "^$TODAY$" "$PROCESSED_DATES_FILE" 2>/dev/null; then
    echo "$(date): Daily update for $TODAY already processed" >> $LOG_FILE
else
    DAILY_URL="https://data.bus-data.dft.gov.uk/timetable/download/change_archive/$TODAY/"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DAILY_URL")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "$(date): ✓ Daily update found for $TODAY!" >> $LOG_FILE
        echo "$TODAY" >> "$PROCESSED_DATES_FILE"
        /home/ubuntu/pt-analytics/txc_processor/process_daily_update.sh "$TODAY" >> $LOG_FILE 2>&1
    else
        echo "$(date): No daily update yet for $TODAY (HTTP $HTTP_CODE)" >> $LOG_FILE
    fi
fi

# ============================================
# 2. CHECK MONTHLY BULK UPDATE
# ============================================
echo "$(date): Checking monthly bulk archive..." >> $LOG_FILE

MONTHLY_URL="https://data.bus-data.dft.gov.uk/timetable/download/bulk_archive/NW"

# Get current file size or ETag (more reliable than Last-Modified)
CURRENT_SIZE=$(curl -sI "$MONTHLY_URL" | grep -i "content-length" | awk '{print $2}' | tr -d '\r')

if [ -z "$CURRENT_SIZE" ]; then
    echo "$(date): Could not get monthly archive size" >> $LOG_FILE
else
    echo "$(date): Monthly archive size: $CURRENT_SIZE bytes" >> $LOG_FILE
    
    # Check if this is first run
    if [ ! -f "$LAST_MONTHLY_CHECK_FILE" ]; then
        echo "$CURRENT_SIZE" > "$LAST_MONTHLY_CHECK_FILE"
        echo "$(date): First run - saved baseline size" >> $LOG_FILE
    else
        LAST_SIZE=$(cat "$LAST_MONTHLY_CHECK_FILE")
        
        if [ "$CURRENT_SIZE" != "$LAST_SIZE" ]; then
            echo "$(date): ✓ Monthly archive changed! ($LAST_SIZE -> $CURRENT_SIZE)" >> $LOG_FILE
            echo "$(date): Triggering full refresh..." >> $LOG_FILE
            
            # Update stored size
            echo "$CURRENT_SIZE" > "$LAST_MONTHLY_CHECK_FILE"
            
            # Trigger full refresh
            /home/ubuntu/pt-analytics/txc_processor/full_refresh.sh >> $LOG_FILE 2>&1
        else
            echo "$(date): Monthly archive unchanged" >> $LOG_FILE
        fi
    fi
fi

echo "$(date): Check complete" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
