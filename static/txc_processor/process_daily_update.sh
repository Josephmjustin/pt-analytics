#!/bin/bash
# Process BODS daily schedule update - INCREMENTAL
# Downloads daily change archive and updates only affected patterns

UPDATE_DATE=$1
BASE_DIR="/home/ubuntu/pt-analytics/static/txc_processor"
DAILY_DIR="$BASE_DIR/daily_updates/$UPDATE_DATE"
LOG_FILE="/var/log/pt-analytics/daily_update.log"
PYTHON="/home/ubuntu/prefect-env/bin/python3"

if [ -z "$UPDATE_DATE" ]; then
    echo "$(date): ERROR - No date provided" >> $LOG_FILE
    exit 1
fi

echo "========================================" >> $LOG_FILE
echo "$(date): Processing daily update for $UPDATE_DATE" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

# Create directory
mkdir -p "$DAILY_DIR"
cd "$DAILY_DIR"

# Daily archive URL (the URL itself is the download)
DAILY_URL="https://data.bus-data.dft.gov.uk/timetable/download/change_archive/$UPDATE_DATE/"
ZIP_FILE="daily_$UPDATE_DATE.zip"

echo "$(date): Downloading from $DAILY_URL" >> $LOG_FILE

# Download the ZIP
wget -q -O "$ZIP_FILE" "$DAILY_URL"

if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Download failed" >> $LOG_FILE
    exit 1
fi

FILE_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "$(date): Downloaded $ZIP_FILE ($FILE_SIZE)" >> $LOG_FILE

# Extract (same nested structure as monthly)
echo "$(date): Extracting..." >> $LOG_FILE
mkdir -p extracted
unzip -q -o "$ZIP_FILE" -d extracted/

# The extracted structure has nested ZIPs per operator, flatten them
echo "$(date): Flattening nested ZIPs..." >> $LOG_FILE
cd extracted

# Find and extract all nested operator ZIPs
for operator_zip in *.zip; do
    if [ -f "$operator_zip" ]; then
        OPERATOR_NAME=$(basename "$operator_zip" .zip)
        mkdir -p "$OPERATOR_NAME"
        unzip -q -o "$operator_zip" -d "$OPERATOR_NAME/"
        
        # Some operators have further nested ZIPs
        find "$OPERATOR_NAME" -name "*.zip" -exec unzip -q -o {} -d "$OPERATOR_NAME/" \;
    fi
done

# Count total XML files
XML_COUNT=$(find . -name "*.xml" | wc -l)
echo "$(date): Extracted $XML_COUNT XML files" >> $LOG_FILE

# Copy extracted files to main txc_processor/extracted directory for processing
MAIN_EXTRACTED="$BASE_DIR/extracted"
rm -rf "$MAIN_EXTRACTED"/*
cp -r . "$MAIN_EXTRACTED/"

cd "$BASE_DIR"

# CRITICAL: Use INCREMENTAL script for daily updates
echo "$(date): Running incremental update (process_daily_incremental.py)..." >> $LOG_FILE
$PYTHON process_daily_incremental.py >> $LOG_FILE 2>&1

if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Processing failed" >> $LOG_FILE
    exit 1
fi

echo "$(date): ✓ Daily incremental update complete!" >> $LOG_FILE

# Cleanup (keep last 7 days)
find "$BASE_DIR/daily_updates" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null

echo "========================================" >> $LOG_FILE
