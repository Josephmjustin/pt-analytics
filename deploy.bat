@echo off
REM deploy.bat - One-command backend deployment
REM Usage: deploy.bat "commit message"

if "%~1"=="" (
    echo Error: Please provide a commit message
    echo Usage: deploy.bat "your commit message"
    exit /b 1
)

set COMMIT_MSG=%~1

echo ========================================
echo PT Analytics Backend Deployment
echo ========================================

echo.
echo [1/4] Committing and pushing to GitHub...
git add .
git commit -m "%COMMIT_MSG%"
git push origin main

echo.
echo [2/4] Updating Oracle VM...
ssh -i %USERPROFILE%\.ssh\oci_pt_analytics ubuntu@141.147.93.150 "cd ~/pt-analytics && git pull origin main"

echo.
echo [3/4] Building Docker image...
docker build -t justinjj94/pt-analytics-api:latest .

echo.
echo [4/4] Deploying to Google Cloud Run...
docker push justinjj94/pt-analytics-api:latest
gcloud run deploy pt-analytics-api --image docker.io/justinjj94/pt-analytics-api:latest --region europe-north1 --allow-unauthenticated

echo.
echo ========================================
echo Backend deployment complete!
echo ========================================
