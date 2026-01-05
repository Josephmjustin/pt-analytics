#!/bin/bash
# Lightweight HEAD checker that triggers GitHub Actions
# Runs every 2 hours on VM #1
# IMPROVED: Only marks as processed after successful completion

set -e

# Configuration - UPDATE GITHUB_TOKEN
GITHUB_REPO="Josephmjustin/pt-analytics"
GITHUB_TOKEN="YOUR_GITHUB_TOKEN"  # Get from https://github.com/settings/tokens

MONTHLY_URL="https://data.bus-data.dft.gov.uk/timetable/download/bulk_archive/NW"
DAILY_URL_TEMPLATE="https://data.bus-data.dft.gov.uk/timetable/download/change_archive/%s/"

BASE_DIR="/home/ubuntu/pt-analytics/static/txc_processor"
LOG_FILE="/var/log/pt-analytics/txc_checker.log"
TRACKING_DIR="$BASE_DIR/tracking"
MONTHLY_SIZE_FILE="$TRACKING_DIR/monthly_size.txt"
MONTHLY_TRIGGER_FILE="$TRACKING_DIR/monthly_triggered.txt"

# Create tracking directory
mkdir -p "$TRACKING_DIR"

echo "========================================" >> "$LOG_FILE"
echo "$(date): TXC Update Check Starting" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Function to trigger GitHub Actions
trigger_github_action() {
    local event_type=$1
    local payload=$2
    
    echo "$(date): Triggering GitHub Action: $event_type" >> "$LOG_FILE"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$GITHUB_REPO/dispatches" \
        -d "{\"event_type\":\"$event_type\",\"client_payload\":$payload}")
    
    if [ "$response" -eq 204 ]; then
        echo "$(date): ✓ GitHub Action triggered successfully" >> "$LOG_FILE"
        return 0
    else
        echo "$(date): ✗ Failed to trigger GitHub Action (HTTP $response)" >> "$LOG_FILE"
        return 1
    fi
}

# Check monthly update
check_monthly() {
    echo "$(date): Checking monthly bulk archive..." >> "$LOG_FILE"
    
    current_month=$(date +%Y-%m)
    
    # Get HEAD
    response=$(curl -s -I "$MONTHLY_URL")
    http_code=$(echo "$response" | grep -i "^HTTP" | awk '{print $2}')
    
    if [ "$http_code" != "200" ]; then
        echo "$(date): ERROR - Could not fetch monthly HEAD (HTTP $http_code)" >> "$LOG_FILE"
        return 1
    fi
    
    # Extract Content-Length
    current_size=$(echo "$response" | grep -i "^Content-Length:" | awk '{print $2}' | tr -d '\r')
    
    if [ -z "$current_size" ]; then
        echo "$(date): ERROR - Could not extract Content-Length" >> "$LOG_FILE"
        return 1
    fi
    
    echo "$(date): Monthly archive size: $current_size bytes" >> "$LOG_FILE"
    
    # Check if already triggered this month
    if [ -f "$MONTHLY_TRIGGER_FILE" ]; then
        triggered_month=$(cat "$MONTHLY_TRIGGER_FILE")
        triggered_size=$(cat "$MONTHLY_SIZE_FILE" 2>/dev/null || echo "0")
        
        # If same month AND same size, skip
        if [ "$triggered_month" == "$current_month" ] && [ "$triggered_size" == "$current_size" ]; then
            echo "$(date): Monthly update already triggered for $current_month (size: $current_size)" >> "$LOG_FILE"
            return 0
        fi
    fi
    
    # Check if size changed from last recorded size
    if [ -f "$MONTHLY_SIZE_FILE" ]; then
        previous_size=$(cat "$MONTHLY_SIZE_FILE")
        
        if [ "$current_size" == "$previous_size" ]; then
            echo "$(date): Monthly archive unchanged ($current_size bytes)" >> "$LOG_FILE"
            return 0
        fi
        
        echo "$(date): Monthly archive CHANGED! ($previous_size -> $current_size bytes)" >> "$LOG_FILE"
    else
        echo "$(date): First check - will trigger processing" >> "$LOG_FILE"
    fi
    
    # Save size and month BEFORE triggering (prevents duplicate triggers)
    echo "$current_size" > "$MONTHLY_SIZE_FILE"
    echo "$current_month" > "$MONTHLY_TRIGGER_FILE"
    
    # Mark as processing (will be changed to 'success' by webhook)
    echo "processing" > "$TRACKING_DIR/monthly_status.txt"
    
    # Trigger GitHub Actions
    trigger_github_action "monthly-update" '{}'
    
    return 0
}

# Check daily update
check_daily() {
    # CRITICAL: Only proceed if monthly processing is complete
    monthly_status="unknown"
    if [ -f "$TRACKING_DIR/monthly_status.txt" ]; then
        monthly_status=$(cat "$TRACKING_DIR/monthly_status.txt")
    fi
    
    if [ "$monthly_status" != "success" ]; then
        echo "$(date): Skipping daily check - monthly status: $monthly_status" >> "$LOG_FILE"
        return 0
    fi
    
    today=$(date +%Y-%m-%d)
    daily_url=$(printf "$DAILY_URL_TEMPLATE" "$today")
    
    echo "$(date): Checking daily update for $today..." >> "$LOG_FILE"
    
    # HEAD check
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$daily_url")
    
    if [ "$http_code" -eq 404 ]; then
        echo "$(date): No daily update yet for $today (HTTP 404)" >> "$LOG_FILE"
        return 0
    elif [ "$http_code" -eq 200 ]; then
        # Check if already processed today
        daily_trigger_file="$TRACKING_DIR/daily_$today.txt"
        
        if [ -f "$daily_trigger_file" ]; then
            echo "$(date): Daily update for $today already triggered" >> "$LOG_FILE"
            return 0
        fi
        
        echo "$(date): Daily update FOUND for $today!" >> "$LOG_FILE"
        
        # Mark as triggered
        touch "$daily_trigger_file"
        
        # Mark as processing
        echo "processing" > "$TRACKING_DIR/daily_status.txt"
        
        # Trigger GitHub Actions
        trigger_github_action "daily-update" "{\"date\":\"$today\"}"
        
        # Cleanup old daily trigger files (keep last 7 days)
        find "$TRACKING_DIR" -name "daily_*.txt" -mtime +7 -delete 2>/dev/null
        
        return 0
    else
        echo "$(date): ERROR - Unexpected HTTP code $http_code for daily check" >> "$LOG_FILE"
        return 1
    fi
}

# Main execution
check_monthly
check_daily

echo "$(date): Check complete" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
