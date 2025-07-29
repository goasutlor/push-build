@echo off
echo 🚀 Flexible Deploy Tool (FastAPI Version)
echo ==========================================

REM Change to the correct directory
cd /d "%~dp0"

echo 🔧 Installing FastAPI dependencies...
python -m pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 pydantic==2.5.0 jinja2==3.1.2 python-multipart==0.0.6 requests==2.31.0

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed successfully!

REM Setup directories
echo 🔧 Setting up directories...
python setup_directories.py

REM Test if app.py exists and has valid syntax
echo 🔍 Testing app.py syntax...
python test_syntax.py

if %ERRORLEVEL% NEQ 0 (
    echo ❌ app.py syntax test failed!
    pause
    exit /b 1
)

echo 🚀 Starting FastAPI application...
echo 📍 Access at: http://localhost:9999
echo 📚 API Docs at: http://localhost:9999/docs

python -m uvicorn app:app --host 0.0.0.0 --port 9999 --reload

pause 