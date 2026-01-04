#!/bin/bash
# Monthly full refresh of schedule data
# TRUNCATES table and reloads all data

BASE_DIR="/home/ubuntu/pt-analytics/static/txc_processor"
LOG_FILE="/var/log/pt-analytics/monthly_refresh.log"
PYTHON="/home/ubuntu/prefect-env/bin/python3"

echo "========================================" >> $LOG_FILE
echo "$(date): MONTHLY FULL REFRESH STARTING" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

cd $BASE_DIR

# 1. Backup current database (optional)
echo "$(date): Creating database backup..." >> $LOG_FILE
# TODO: Add pg_dump backup if needed

# 2. Clean all extracted files
echo "$(date): Cleaning all extracted files..." >> $LOG_FILE
rm -rf $BASE_DIR/extracted/*

# 3. Download fresh data
echo "$(date): Downloading TransXChange data..." >> $LOG_FILE
$PYTHON download_txc.py >> $LOG_FILE 2>&1

if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Download failed" >> $LOG_FILE
    exit 1
fi

# 4. Process and load to database (TRUNCATE + full reload)
echo "$(date): Processing schedules (full TRUNCATE + reload)..." >> $LOG_FILE
$PYTHON create_schedule_efficient.py >> $LOG_FILE 2>&1

if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Processing failed" >> $LOG_FILE
    exit 1
fi

# 5. Verify data loaded
echo "$(date): Verifying database..." >> $LOG_FILE
RECORD_COUNT=$(PGPASSWORD=$ORACLE_VM2_PASSWORD psql -h 141.147.106.59 -U pt_api -d pt_analytics_schedules -tAc "SELECT COUNT(*) FROM stop_schedule" 2>/dev/null)

if [ -n "$RECORD_COUNT" ]; then
    echo "$(date): Total schedule records: $RECORD_COUNT" >> $LOG_FILE
    
    if [ $RECORD_COUNT -lt 1000000 ]; then
        echo "$(date): WARNING - Record count seems low!" >> $LOG_FILE
    fi
else
    echo "$(date): Could not verify record count" >> $LOG_FILE
fi

echo "$(date): Monthly refresh complete!" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
