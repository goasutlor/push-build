# 🚀 Flexible Deploy Tool - Quick Start Guide

## Overview
The Flexible Deploy Tool is a universal deployment pipeline that can detect and deploy any type of project. It provides a web interface for scanning directories, managing GitHub repositories, and deploying projects.

## 🎯 Current Status
✅ **Fixed Issues:**
- Project detection now properly excludes `.git` and other non-project directories
- Frontend now correctly displays detected projects
- Added missing `createProjectCard` function
- Improved logging and error handling

## 🚀 How to Use

### 1. Start the Application
```bash
# Run the application
python -m uvicorn app:app --host 0.0.0.0 --port 9999 --reload

# Or use the provided batch file
run.bat
```

### 2. Access the Web Interface
- Open your browser and go to: `http://localhost:9999`
- You'll see the Flexible Deploy Tool interface

### 3. Scan for Projects
1. **Go to the "Projects" tab**
2. **Enter a directory path** (e.g., `D:\Project1`)
3. **Click "Scan Projects"**
4. **View detected projects** - you should now see 4 projects:
   - Complete_Deploy_Tool
   - Complete_Deploy_Tool_fastapi
   - vm_provisioning
   - vm_provisioning_fastapi

### 4. Project Features
Each project card shows:
- 📁 Project name and type
- 🔗 Git repository status
- 📦 Requirements file presence
- 🐳 Dockerfile availability
- 📂 Project path

### 5. Select and Deploy
1. **Click on a project** to select it
2. **Go to the "Deploy" tab**
3. **Fill in deployment details:**
   - GitHub username and token
   - Target repository
   - Version information
4. **Click "Deploy"** to start the deployment process

## 🔧 Features

### Project Detection
- ✅ Detects Flask/FastAPI projects
- ✅ Detects Node.js projects
- ✅ Detects Java projects
- ✅ Detects Rust projects
- ✅ Detects Go projects
- ✅ Detects Docker projects
- ✅ Excludes non-project directories (`.git`, `__pycache__`, etc.)

### GitHub Integration
- 🔗 Connect to GitHub repositories
- 📋 List user repositories
- ➕ Create new repositories
- 🚀 Deploy to selected repositories

### Real-time Logging
- 📡 Stream deployment logs
- 🔍 Debug tools for troubleshooting
- 📋 View all deployment history

### Docker Support
- 🐳 Check Docker images in GitHub Container Registry
- 💻 Check local Docker images
- 📊 Compare GitHub vs local images

## 🛠️ Troubleshooting

### No Projects Found?
1. **Check the directory path** - make sure it exists
2. **Verify the directory contains project files** (app.py, requirements.txt, Dockerfile, etc.)
3. **Check the logs** in the "Logs" tab for any errors

### Application Not Starting?
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Check port availability:** Make sure port 9999 is not in use
3. **Run with admin privileges** if needed

### Deployment Issues?
1. **Verify GitHub credentials** in the "Debug" tab
2. **Check repository permissions** - make sure you have write access
3. **Review deployment logs** for specific error messages

## 📁 Project Structure
```
Complete_Deploy_Tool_fastapi/
├── app.py                 # Main FastAPI application
├── templates/
│   └── index.html        # Web interface
├── static/               # Static files
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── run.bat             # Windows startup script
└── README.md           # Documentation
```

## 🎉 Success!
The application should now properly detect and display your projects. You can:
- ✅ Scan directories for projects
- ✅ View project details and features
- ✅ Select projects for deployment
- ✅ Deploy to GitHub repositories
- ✅ Monitor deployment progress

For more information, see the main README.md file. 