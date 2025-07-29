@echo off
echo Building Docker Image for Flexible Deploy Tool...
echo.

echo Checking Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker not found. Please install Docker Desktop first.
    pause
    exit /b 1
)

echo ✅ Docker found
echo.

echo Building image...
docker build -t flexible-deploy-tool:latest .

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker build failed
    pause
    exit /b 1
)

echo.
echo ✅ Docker image built successfully!
echo.
echo 🚀 To run the container with volume mount:
echo    docker run -p 9998:9998 flexible-deploy-tool:latest
echo.
echo 🐳 To run with Docker Compose:
echo    docker-compose up -d
echo.
echo 📋 To see running containers:
echo    docker ps
echo.
pause 