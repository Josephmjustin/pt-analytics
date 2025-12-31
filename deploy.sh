#!/bin/bash
# deploy.sh - One-command backend deployment
# Usage: ./deploy.sh "commit message"

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for commit message
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a commit message${NC}"
    echo "Usage: ./deploy.sh \"your commit message\""
    exit 1
fi

COMMIT_MSG="$1"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}PT Analytics Backend Deployment${NC}"
echo -e "${YELLOW}========================================${NC}"

# Step 1: Git commit and push
echo -e "\n${GREEN}[1/4] Committing and pushing to GitHub...${NC}"
git add .
git commit -m "$COMMIT_MSG" || echo "Nothing to commit"
git push origin main

# Step 2: Update Oracle VM (cron jobs)
echo -e "\n${GREEN}[2/4] Updating Oracle VM...${NC}"
ssh -i ~/.ssh/oci_pt_analytics ubuntu@141.147.93.150 "cd ~/pt-analytics && git pull origin main"

# Step 3: Build Docker image
echo -e "\n${GREEN}[3/4] Building Docker image...${NC}"
docker build -t justinjj94/pt-analytics-api:latest .

# Step 4: Push and deploy to Google Cloud Run
echo -e "\n${GREEN}[4/4] Deploying to Google Cloud Run...${NC}"
docker push justinjj94/pt-analytics-api:latest
gcloud run deploy pt-analytics-api \
  --image docker.io/justinjj94/pt-analytics-api:latest \
  --region europe-north1 \
  --allow-unauthenticated

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Backend deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
