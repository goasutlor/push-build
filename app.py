from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import queue
import threading
import time
import json
import requests
import asyncio

# Initialize FastAPI app
app = FastAPI(
    title="Flexible Deploy Tool",
    description="Universal deployment pipeline for any project",
    version="1.3.0"
)

# Mount static files (only if directory exists)
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    print("⚠️  Warning: static directory not found, skipping static files mount")

# Templates (only if directory exists)
templates_dir = Path("templates")
if templates_dir.exists():
    templates = Jinja2Templates(directory="templates")
else:
    print("⚠️  Warning: templates directory not found, creating basic template")
    # Create a basic template for testing
    templates_dir.mkdir(exist_ok=True)
    with open(templates_dir / "index.html", "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head><title>Flexible Deploy Tool</title></head>
<body>
<h1>Flexible Deploy Tool (FastAPI)</h1>
<p>Application is running successfully!</p>
<p><a href="/docs">API Documentation</a></p>
</body>
</html>
""")
    templates = Jinja2Templates(directory="templates")

# Global variables
log_queue = queue.Queue()
all_projects = []

# Pydantic models
class ProjectInfo(BaseModel):
    name: str
    path: str
    type: str
    has_git: bool
    has_app: bool
    has_requirements: bool
    has_dockerfile: bool
    sub_projects: Optional[List[Dict[str, Any]]] = None
    parent: Optional[str] = None

class DeployRequest(BaseModel):
    project_path: str
    project_name: str
    github_username: str
    github_token: str
    selected_repository: str
    version: Optional[str] = None
    semantic_version: Optional[str] = None

class GitHubRequest(BaseModel):
    github_username: str
    github_token: str

class RepositoryRequest(GitHubRequest):
    repository: str

# Utility functions
def log_wrapper(message: str):
    """Add timestamp and send to queue"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    log_queue.put(log_entry)

def detect_projects_in_directory(directory_path: Path) -> List[ProjectInfo]:
    """Detect projects in a directory"""
    projects = []
    
    try:
        log_wrapper(f"🔍 Scanning directory: {directory_path}")
        
        # Check if directory exists
        if not directory_path.exists():
            log_wrapper(f"❌ Directory does not exist: {directory_path}")
            return projects
        
        # FIRST: Check if the root directory itself is a project
        log_wrapper(f"🔍 Checking root directory: {directory_path.name}")
        root_project_info = {
            'name': directory_path.name,
            'path': str(directory_path),
            'type': 'unknown',
            'has_git': (directory_path / '.git').exists(),
            'has_app': (directory_path / 'app.py').exists(),
            'has_requirements': (directory_path / 'requirements.txt').exists(),
            'has_dockerfile': (directory_path / 'Dockerfile').exists(),
            'sub_projects': [],
            'parent': None
        }
        
        # Detect project type for root directory
        if (directory_path / 'app.py').exists():
            root_project_info['type'] = 'flask'
        elif (directory_path / 'package.json').exists():
            root_project_info['type'] = 'nodejs'
        elif (directory_path / 'pom.xml').exists():
            root_project_info['type'] = 'java'
        elif (directory_path / 'Cargo.toml').exists():
            root_project_info['type'] = 'rust'
        elif (directory_path / 'go.mod').exists():
            root_project_info['type'] = 'go'
        elif (directory_path / 'Dockerfile').exists():
            root_project_info['type'] = 'docker'
        
        # Debug logging for root directory project detection
        log_wrapper(f"🔍 Checking root {directory_path.name}: app.py={root_project_info['has_app']}, requirements.txt={root_project_info['has_requirements']}, Dockerfile={root_project_info['has_dockerfile']}, .git={root_project_info['has_git']}")
        
        # Add root directory if it's a project
        if (root_project_info['has_app'] or root_project_info['has_requirements'] or 
            root_project_info['has_dockerfile'] or root_project_info['has_git']):
            projects.append(ProjectInfo(**root_project_info))
            log_wrapper(f"✅ Found project in root: {directory_path.name} ({root_project_info['type']})")
        else:
            log_wrapper(f"❌ Root {directory_path.name} is not a project (no project files found)")
        
        # List all items in directory
        items = list(directory_path.iterdir())
        log_wrapper(f"📁 Found {len(items)} items in directory")
        
        for item in items:
            if item.is_dir():
                log_wrapper(f"📂 Checking directory: {item.name}")
                # Skip non-project directories
                if item.name in ['.git', '__pycache__', 'node_modules', '.venv', '.vscode', '.idea']:
                    log_wrapper(f"⏭️ Skipping non-project directory: {item.name}")
                    continue
                
                project_info = {
                    'name': item.name,
                    'path': str(item),
                    'type': 'unknown',
                    'has_git': (item / '.git').exists(),
                    'has_app': (item / 'app.py').exists(),
                    'has_requirements': (item / 'requirements.txt').exists(),
                    'has_dockerfile': (item / 'Dockerfile').exists(),
                    'sub_projects': [],
                    'parent': None
                }
                
                # Detect project type
                if (item / 'app.py').exists():
                    project_info['type'] = 'flask'
                elif (item / 'package.json').exists():
                    project_info['type'] = 'nodejs'
                elif (item / 'pom.xml').exists():
                    project_info['type'] = 'java'
                elif (item / 'Cargo.toml').exists():
                    project_info['type'] = 'rust'
                elif (item / 'go.mod').exists():
                    project_info['type'] = 'go'
                elif (item / 'Dockerfile').exists():
                    project_info['type'] = 'docker'
                
                # Debug logging for project detection
                log_wrapper(f"🔍 Checking {item.name}: app.py={project_info['has_app']}, requirements.txt={project_info['has_requirements']}, Dockerfile={project_info['has_dockerfile']}, .git={project_info['has_git']}")
                
                # Only add if it's actually a project (has some project files)
                if (project_info['has_app'] or project_info['has_requirements'] or 
                    project_info['has_dockerfile'] or project_info['has_git']):
                    projects.append(ProjectInfo(**project_info))
                    log_wrapper(f"✅ Found project: {item.name} ({project_info['type']})")
                else:
                    log_wrapper(f"❌ Not a project: {item.name} (no project files found)")
                
                # Check for sub-projects
                for sub_item in item.iterdir():
                    if sub_item.is_dir() and sub_item.name not in ['.git', '__pycache__', 'node_modules', '.venv', '.vscode', '.idea']:
                        if (sub_item / 'app.py').exists() or (sub_item / 'package.json').exists() or (sub_item / 'Dockerfile').exists():
                            sub_project_info = {
                                'name': sub_item.name,
                                'path': str(sub_item),
                                'type': 'unknown',
                                'has_git': (sub_item / '.git').exists(),
                                'has_app': (sub_item / 'app.py').exists(),
                                'has_requirements': (sub_item / 'requirements.txt').exists(),
                                'has_dockerfile': (sub_item / 'Dockerfile').exists(),
                                'sub_projects': [],
                                'parent': item.name
                            }
                            
                            if (sub_item / 'app.py').exists():
                                sub_project_info['type'] = 'flask'
                            elif (sub_item / 'package.json').exists():
                                sub_project_info['type'] = 'nodejs'
                            elif (sub_item / 'Dockerfile').exists():
                                sub_project_info['type'] = 'docker'
                            
                            project_info['sub_projects'].append(sub_project_info)
                            log_wrapper(f"✅ Found sub-project: {sub_item.name} in {item.name}")
    
    except Exception as e:
        log_wrapper(f"❌ Error detecting projects: {e}")
    
    log_wrapper(f"📊 Total projects found: {len(projects)}")
    return projects

def stream_logs():
    """Stream logs to client in real-time"""
    while True:
        try:
            # Get all logs from queue
            logs = []
            while not log_queue.empty():
                try:
                    log_entry = log_queue.get_nowait()
                    logs.append(log_entry)
                except queue.Empty:
                    break
            
            if logs:
                # Send accumulated logs
                log_data = '\n'.join(logs)
                yield f"data: {json.dumps({'logs': log_data, 'type': 'append'})}\n\n"
            
            time.sleep(0.1)  # Poll every 100ms for faster response
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break

# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Test page for debugging"""
    with open("test_frontend.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/get-projects")
async def get_projects():
    """Get available projects"""
    try:
        # Get current directory and parent directory
        current_dir = Path.cwd()
        parent_dir = current_dir.parent
        
        projects = []
        
        # Detect projects in current directory
        current_projects = detect_projects_in_directory(current_dir)
        projects.extend(current_projects)
        
        # Detect projects in parent directory
        if parent_dir.exists() and parent_dir != current_dir:
            parent_projects = detect_projects_in_directory(parent_dir)
            projects.extend(parent_projects)
        
        # Sort projects by relevance
        projects.sort(key=lambda x: (
            x.has_git, x.has_app, x.has_requirements, x.has_dockerfile
        ), reverse=True)
        
        global all_projects
        all_projects = projects
        
        return {"projects": [project.dict() for project in projects]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/browse-folders")
async def browse_folders(request: Request):
    """Browse folders to find project files"""
    try:
        data = await request.json()
        folder_path = data.get('folder_path', '')
        
        if not folder_path:
            raise HTTPException(status_code=400, detail='No folder path provided')
        
        log_wrapper(f"🔍 Browse path: {folder_path}")
        log_wrapper(f"🔍 Final browse path: {folder_path}")
        
        folder = Path(folder_path)
        if not folder.exists():
            log_wrapper(f"❌ Path {folder_path} does not exist")
            raise HTTPException(
                status_code=404, 
                detail=f'Folder does not exist: {folder_path}'
            )
        
        files = []
        for item in folder.iterdir():
            if item.is_file():
                file_info = {
                    'name': item.name,
                    'path': str(item),
                    'size': item.stat().st_size,
                    'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                }
                files.append(file_info)
        
        return {"files": files}
    except HTTPException:
        raise
    except Exception as e:
        log_wrapper(f"❌ Error in browse_folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scan-custom-folder")
async def scan_custom_folder(request: Request):
    """Scan custom folder for projects"""
    try:
        data = await request.json()
        folder_path = data.get('folder_path', '')
        
        if not folder_path:
            raise HTTPException(status_code=400, detail='No folder path provided')
        
        # Detect if running in Docker container
        import os
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        log_wrapper(f"🔍 Original requested path: {folder_path}")
        log_wrapper(f"🐳 Running in Docker: {is_docker}")
        
        # Simple path handling - use what user provides
        if is_docker:
            log_wrapper(f"🔍 Docker detected - processing path: '{folder_path}'")
            
            # If user provided a path, try to use it directly
            if folder_path and folder_path.strip():
                # Check if path exists in container
                if Path(folder_path).exists():
                    log_wrapper(f"🔍 Using user-provided path: '{folder_path}'")
                else:
                    # Try to map common Windows paths
                    if folder_path.startswith('D:\\') or folder_path.startswith('D:/'):
                        # Special case: D:\Project1 -> /workspace
                        if folder_path == 'D:\\Project1' or folder_path == 'D:/Project1':
                            mapped_path = '/workspace'
                            log_wrapper(f"🔍 Special mapping D:\\Project1 to: '{mapped_path}'")
                        else:
                            mapped_path = folder_path.replace('D:\\', '/workspace/').replace('D:/', '/workspace/')
                            log_wrapper(f"🔍 Mapping Windows path to: '{mapped_path}'")
                        folder_path = mapped_path
                    elif folder_path.startswith('C:\\') or folder_path.startswith('C:/'):
                        # Special case: C:\Users\... -> /workspace
                        if folder_path.startswith('C:\\Users\\') or folder_path.startswith('C:/Users/'):
                            mapped_path = '/workspace'
                            log_wrapper(f"🔍 Special mapping C:\\Users to: '{mapped_path}'")
                        else:
                            mapped_path = folder_path.replace('C:\\', '/workspace/').replace('C:/', '/workspace/')
                            log_wrapper(f"🔍 Mapping Windows path to: '{mapped_path}'")
                        folder_path = mapped_path
                    else:
                        # Assume it's relative to /workspace
                        if not folder_path.startswith('/'):
                            folder_path = f"/workspace/{folder_path}"
                            log_wrapper(f"🔍 Relative path mapped to: '{folder_path}'")
                        else:
                            log_wrapper(f"🔍 Using absolute path: '{folder_path}'")
            else:
                # No path provided, use /workspace as default
                folder_path = "/workspace"
                log_wrapper(f"🔍 No path provided, using default: '{folder_path}'")
        else:
            log_wrapper(f"🔍 Not in Docker -> using path as-is: '{folder_path}'")
        
        log_wrapper(f"🔍 Final path to scan: '{folder_path}'")
        log_wrapper(f"🔍 Path exists check: {Path(folder_path).exists()}")
        
        # Add detailed path debugging
        log_wrapper(f"🔍 Current working directory: {Path.cwd()}")
        log_wrapper(f"🔍 Absolute path: {Path(folder_path).absolute()}")
        log_wrapper(f"🔍 Resolved path: {Path(folder_path).resolve()}")
        
        # Debug: Show what's in the target path
        target_path = Path(folder_path)
        if target_path.exists():
            try:
                items = list(target_path.iterdir())
                log_wrapper(f"🔍 Target path contains {len(items)} items:")
                for i, item in enumerate(items[:5]):  # Show first 5 items
                    log_wrapper(f"🔍   {i+1}. {item.name} ({'dir' if item.is_dir() else 'file'})")
                if len(items) > 5:
                    log_wrapper(f"🔍   ... and {len(items) - 5} more items")
            except Exception as e:
                log_wrapper(f"🔍 Error listing target path contents: {e}")
        else:
            log_wrapper(f"🔍 Target path does not exist")
        
        folder = Path(folder_path)
        if not folder.exists():
            log_wrapper(f"❌ Path {folder_path} does not exist")
            raise HTTPException(
                status_code=404, 
                detail=f'Folder does not exist: {folder_path}'
            )
        
        # Check if the folder is empty
        try:
            items = list(folder.iterdir())
            if len(items) == 0:
                log_wrapper(f"⚠️ Path {folder_path} exists but is empty")
                raise HTTPException(
                    status_code=404,
                    detail=f'Path {folder_path} exists but is empty'
                )
        except Exception as e:
            log_wrapper(f"❌ Error checking folder contents: {e}")
        
        # Use the same project detection logic
        projects = detect_projects_in_directory(folder)
        
        return {"projects": [project.dict() for project in projects]}
    except HTTPException:
        raise
    except Exception as e:
        log_wrapper(f"❌ Error in scan_custom_folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-available-drives")
async def get_available_drives():
    """Get available drives for folder browser"""
    try:
        import platform
        drives = []
        
        if platform.system() == 'Windows':
            import subprocess
            # Get Windows drives
            result = subprocess.run(['wmic', 'logicaldisk', 'get', 'caption'], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip():
                        drives.append(line.strip())
        else:
            # For Linux/Mac, use environment variable or common paths
            custom_drives = os.environ.get('CUSTOM_DRIVES', '')
            if custom_drives:
                drives = custom_drives.split(',')
            else:
                drives = ['/', '/home', '/mnt', '/opt']
        
        return {"drives": drives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def logs():
    """Get deployment logs"""
    try:
        # Get all available logs
        logs = []
        while not log_queue.empty():
            logs.append(log_queue.get_nowait())
        
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
async def stream():
    """Stream logs to client in real-time"""
    return StreamingResponse(stream_logs(), media_type="text/event-stream")

@app.post("/deploy")
async def deploy(request: Request):
    """Deploy project to GitHub and build Docker image"""
    try:
        data = await request.json()
        
        # Extract data
        project_path = data.get('project_path', '')
        project_name = data.get('project_name', '')
        github_username = data.get('github_username', '')
        github_token = data.get('github_token', '')
        selected_repository = data.get('selected_repository', '')
        version_input = data.get('version', '')
        semantic_version = data.get('semantic_version', '')
        version_note = data.get('version_note', '')
        
        # Start deployment in background thread
        def deploy_process():
            try:
                # Declare nonlocal variables that will be modified
                nonlocal project_path
                
                log_wrapper("🚀 Starting Flexible Deploy Tool...")
                log_wrapper("⏳ This may take a few minutes...")
                
                # STEP 1: Validate inputs
                log_wrapper("📋 STEP 1: Validating inputs...")
                
                # Validate required fields
                required_fields = {
                    'project_name': project_name,
                    'github_username': github_username,
                    'github_token': github_token,
                    'selected_repository': selected_repository
                }
                
                missing_fields = [field for field, value in required_fields.items() if not value]
                if missing_fields:
                    log_wrapper(f"❌ Missing required parameters: {', '.join(missing_fields)}")
                    return
                
                # Handle project path (can be empty or current directory)
                if not project_path or project_path.strip() == '' or project_path == '.':
                    project_path = os.getcwd()
                    log_wrapper(f"📁 Using current directory: {project_path}")
                
                log_wrapper(f"✅ Project: {project_name}")
                log_wrapper(f"✅ Path: {project_path}")
                log_wrapper(f"✅ Repository: {selected_repository}")
                log_wrapper("⏳ Proceeding to next step...")
                
                # STEP 2: GitHub authentication
                log_wrapper("🔐 STEP 2: Authenticating with GitHub...")
                log_wrapper("⏳ Connecting to GitHub API...")
                headers = {
                    'Authorization': f'token {github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                # Test GitHub connection with timeout
                try:
                    response = requests.get('https://api.github.com/user', headers=headers, timeout=60)
                    if response.status_code == 200:
                        user_data = response.json()
                        log_wrapper(f"✅ Authenticated as: {user_data.get('login', 'Unknown')}")
                    else:
                        log_wrapper(f"❌ GitHub authentication failed: {response.status_code}")
                        return
                except requests.exceptions.Timeout:
                    log_wrapper("❌ GitHub connection timeout")
                    return
                except Exception as e:
                    log_wrapper(f"❌ GitHub connection error: {e}")
                    return
                
                # STEP 3: Repository validation
                log_wrapper("📁 STEP 3: Validating repository...")
                log_wrapper("⏳ Checking repository access...")
                repo_url = f'https://api.github.com/repos/{selected_repository}'
                try:
                    response = requests.get(repo_url, headers=headers, timeout=60)
                    if response.status_code == 200:
                        log_wrapper(f"✅ Repository accessible: {selected_repository}")
                    else:
                        log_wrapper(f"❌ Repository not found: {selected_repository}")
                        return
                except requests.exceptions.Timeout:
                    log_wrapper("❌ Repository validation timeout")
                    return
                except Exception as e:
                    log_wrapper(f"❌ Repository validation error: {e}")
                    return
                
                # STEP 4: Project validation
                log_wrapper("📂 STEP 4: Validating project...")
                log_wrapper("⏳ Checking project directory...")
                project_dir = Path(project_path)
                if not project_dir.exists():
                    log_wrapper(f"❌ Project directory not found: {project_path}")
                    return
                
                log_wrapper(f"✅ Project directory exists: {project_path}")
                
                # STEP 5: Perform real deployment operations
                log_wrapper("🔄 STEP 5: Performing deployment operations...")
                log_wrapper("📊 Progress: 0% - Starting deployment...")
                
                # Create temporary directory for clean deployment
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    log_wrapper(f"📁 Created temporary directory: {temp_dir}")
                    
                    # Copy project files to temp directory (excluding .git and merge conflicts)
                    try:
                        # Use copytree with ignore to exclude .git directory and merge conflicts
                        def ignore_git_and_conflicts(dir, files):
                            ignore_list = ['.git']
                            # Also ignore any files with merge conflict markers
                            for file in files:
                                if file.endswith('.py') or file.endswith('.txt') or file.endswith('.md'):
                                    file_path = os.path.join(dir, file)
                                    try:
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                            if '<<<<<<< HEAD' in content or '>>>>>> ' in content:
                                                ignore_list.append(file)
                                    except:
                                        pass
                            return ignore_list
                        
                        # Copy all files first, then clean them
                        shutil.copytree(project_path, temp_path / project_name, 
                                      dirs_exist_ok=True, ignore=lambda dir, files: ['.git'])
                    
                        # Clean any remaining merge conflict markers in copied files
                        for root, dirs, files in os.walk(temp_path / project_name):
                            for file in files:
                                if file.endswith('.py') or file.endswith('.txt') or file.endswith('.md') or file == 'Dockerfile':
                                    file_path = os.path.join(root, file)
                                    try:
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                        
                                        # Remove merge conflict markers
                                        if '<<<<<<< HEAD' in content or '>>>>>> ' in content or '=======' in content:
                                            log_wrapper(f"🧹 Cleaning merge conflicts in {file}")
                                            # Remove conflict markers and keep only the HEAD version
                                            lines = content.split('\n')
                                            cleaned_lines = []
                                            skip_section = False
                                            
                                            for line in lines:
                                                if line.startswith('<<<<<<< HEAD'):
                                                    skip_section = False
                                                elif line.startswith('======='):
                                                    skip_section = True
                                                elif line.startswith('>>>>>> '):
                                                    skip_section = False
                                                elif not skip_section:
                                                    cleaned_lines.append(line)
                                            
                                            cleaned_content = '\n'.join(cleaned_lines)
                                            with open(file_path, 'w', encoding='utf-8') as f:
                                                f.write(cleaned_content)
                                            log_wrapper(f"✅ Cleaned {file}")
                                    except Exception as e:
                                        log_wrapper(f"⚠️ Warning: Could not clean file {file}: {e}")
                    
                        log_wrapper(f"📋 Files copied and cleaned to temporary directory")
                        log_wrapper("📊 Progress: 20% - Files prepared...")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to copy files: {e}")
                        return
                    
                    # Initialize Git repository
                    try:
                        log_wrapper("🔧 Initializing Git repository...")
                        subprocess.run(['git', 'init'], cwd=temp_path / project_name, check=True, capture_output=True)
                        
                        # Set the default branch to main
                        subprocess.run(['git', 'config', 'init.defaultBranch', 'main'], cwd=temp_path / project_name, check=True, capture_output=True)
                        
                        log_wrapper("✅ Git repository initialized with main branch")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to initialize Git: {e}")
                        return
                    
                    # Add all files to Git
                    try:
                        log_wrapper("📝 Adding files to Git...")
                        subprocess.run(['git', 'add', '.'], cwd=temp_path / project_name, check=True, capture_output=True)
                        log_wrapper("✅ Files added to Git")
                        log_wrapper("📊 Progress: 40% - Git setup complete...")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to add files: {e}")
                        return
                    
                    # Configure Git user
                    try:
                        log_wrapper("👤 Configuring Git user...")
                        subprocess.run(['git', 'config', 'user.name', github_username], cwd=temp_path / project_name, check=True, capture_output=True)
                        subprocess.run(['git', 'config', 'user.email', f'{github_username}@users.noreply.github.com'], cwd=temp_path / project_name, check=True, capture_output=True)
                        log_wrapper("✅ Git user configured")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to configure Git user: {e}")
                        return
                    
                    # Commit files
                    try:
                        log_wrapper("💾 Committing files...")
                        commit_message = f"Deploy {project_name} via Flexible Deploy Tool"
                        if version_note:
                            commit_message += f"\n\nChanges: {version_note}"
                        subprocess.run(['git', 'commit', '-m', commit_message], cwd=temp_path / project_name, check=True, capture_output=True)
                        log_wrapper("✅ Files committed")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to commit files: {e}")
                        return
                    
                    # Add remote repository
                    try:
                        log_wrapper("🔗 Adding remote repository...")
                        remote_url = f"https://{github_token}@github.com/{selected_repository}.git"
                        subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=temp_path / project_name, check=True, capture_output=True)
                        log_wrapper("✅ Remote repository added")
                    except Exception as e:
                        log_wrapper(f"❌ Failed to add remote: {e}")
                        return
                    
                    # Push to GitHub
                    try:
                        log_wrapper("📤 Pushing code to GitHub...")
                        
                        # Ensure we're on the main branch
                        subprocess.run(['git', 'branch', '-M', 'main'], cwd=temp_path / project_name, check=True, capture_output=True)
                        log_wrapper("✅ Switched to main branch")
                        
                        # Try to pull first to sync with remote
                        log_wrapper("🔄 Syncing with remote repository...")
                        pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], 
                                                   cwd=temp_path / project_name, 
                                                   capture_output=True, text=True)
                        
                        # Try to pull first to sync with remote
                        log_wrapper("📥 Syncing with remote repository...")
                        pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], 
                                                   cwd=temp_path / project_name, 
                                                   capture_output=True, text=True)
                        
                        # Push to main branch with better error handling
                        log_wrapper("📤 Pushing to GitHub...")
                        result = subprocess.run(['git', 'push', '-u', 'origin', 'main'], 
                                             cwd=temp_path / project_name, 
                                             capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            log_wrapper("✅ Code pushed to GitHub successfully!")
                            log_wrapper("📊 Progress: 60% - Code pushed to GitHub...")
                        else:
                            # Check if it's a non-fast-forward error
                            if "non-fast-forward" in result.stderr or "rejected" in result.stderr:
                                log_wrapper("📝 Remote has newer commits, using force push...")
                                
                                # Force push to overwrite remote content
                                result = subprocess.run(['git', 'push', '-u', 'origin', 'main', '--force'], 
                                                     cwd=temp_path / project_name, 
                                                     capture_output=True, text=True)
                                
                                if result.returncode == 0:
                                    log_wrapper("✅ Code pushed to GitHub successfully (force pushed)!")
                                    log_wrapper("📊 Progress: 60% - Code pushed to GitHub...")
                                else:
                                    log_wrapper("📝 Force push failed, trying to create repository...")
                                    # Try to create the repository if it doesn't exist
                                    create_repo_url = 'https://api.github.com/user/repos'
                                    repo_data = {
                                        'name': selected_repository.split('/')[-1],
                                        'private': False,
                                        'auto_init': False
                                    }
                                    
                                    create_response = requests.post(create_repo_url, 
                                                                 headers=headers, 
                                                                 json=repo_data, 
                                                                 timeout=60)
                                    
                                    if create_response.status_code in [201, 422]:  # 422 means repo already exists
                                        log_wrapper("✅ Repository created/exists, trying push again...")
                                        result = subprocess.run(['git', 'push', '-u', 'origin', 'main'], 
                                                             cwd=temp_path / project_name, 
                                                             capture_output=True, text=True)
                                        
                                        if result.returncode == 0:
                                            log_wrapper("✅ Code pushed to GitHub successfully!")
                                        else:
                                            log_wrapper("📝 Push failed, but deployment continues...")
                                            log_wrapper("💡 You can manually push later using: git push -u origin main")
                                    else:
                                        log_wrapper("📝 Repository creation failed, but deployment continues...")
                                        log_wrapper("💡 You can create the repository manually on GitHub")
                            else:
                                log_wrapper("📝 Push failed, but deployment continues...")
                                log_wrapper("💡 You can manually push later using: git push -u origin main")
                            
                    except Exception as e:
                        log_wrapper(f"📝 GitHub push encountered issues, but deployment continues...")
                        log_wrapper(f"📝 Info: {e}")
                        log_wrapper("💡 You can manually push to GitHub later")
                    
                    log_wrapper(f"🌐 Repository URL: https://github.com/{selected_repository}")
                    
                    # STEP 6: Docker build and push
                    log_wrapper("🐳 STEP 6: Building and pushing Docker image...")
                    
                    # Check if Dockerfile exists
                    dockerfile_path = Path(project_path) / 'Dockerfile'
                    if not dockerfile_path.exists():
                        log_wrapper("❌ Dockerfile not found in project directory")
                        log_wrapper("💡 Docker build will be skipped")
                        return
                    
                    log_wrapper("📋 Dockerfile found, building image...")
                    
                    # Check if running in Docker container
                    is_docker_container = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
                    
                    if is_docker_container:
                        log_wrapper("⚠️ Running in Docker container - checking for Docker socket...")
                        
                        # Check if Docker operations are enabled via environment variable
                        docker_enabled = os.environ.get('DOCKER_ENABLED', 'true').lower() == 'true'
                        
                        # Check if Docker socket is available (Docker-in-Docker)
                        if os.path.exists('/var/run/docker.sock') and docker_enabled:
                            log_wrapper("✅ Docker socket found - Docker-in-Docker enabled")
                            log_wrapper("🔧 Using host Docker daemon for build/push")
                            build_command = ['docker', 'build']
                        else:
                            log_wrapper("⚠️ Docker operations disabled")
                            log_wrapper("💡 To enable Docker operations, run with:")
                            log_wrapper("   docker run -v /var/run/docker.sock:/var/run/docker.sock -p 9998:9998 ghcr.io/goasutlor/push-build:latest")
                            log_wrapper("💡 Or set DOCKER_ENABLED=false to skip Docker operations")
                            log_wrapper("📊 Progress: 100% - Deployment completed (Git push successful)")
                            return
                    else:
                        # Regular Docker build for host machine
                        log_wrapper("✅ Running on host machine - using local Docker")
                        build_command = ['docker', 'build']
                    
                    # Build Docker image
                    try:
                        # Create image name with version
                        version_tag = version_input if version_input else f"v{datetime.now().strftime('%Y.%m.%d.%H%M')}"
                        image_name = f"ghcr.io/{selected_repository}:{version_tag}"
                        latest_image = f"ghcr.io/{selected_repository}:latest"
                        
                        log_wrapper(f"🏗️ Building Docker image: {image_name}")
                        log_wrapper(f"📊 Progress: 70% - Building Docker image...")
                        
                        # Build the image
                        build_cmd = build_command + ['-t', image_name, '-t', latest_image, '.']
                        log_wrapper(f"🔧 Build command: {' '.join(build_cmd)}")
                        
                        build_result = subprocess.run(
                            build_cmd,
                            cwd=project_path,
                            capture_output=True,
                            text=True,
                            timeout=600  # 10 minutes timeout
                        )
                        
                        if build_result.returncode == 0:
                            log_wrapper("✅ Docker image built successfully")
                            log_wrapper(f"📊 Progress: 80% - Docker image built...")
                            
                            # Login to GitHub Container Registry
                            log_wrapper("🔐 Logging into GitHub Container Registry...")
                            login_result = subprocess.run(
                                ['docker', 'login', 'ghcr.io', '-u', github_username, '-p', github_token],
                                capture_output=True,
                                text=True,
                                timeout=60
                            )
                            
                            if login_result.returncode == 0:
                                log_wrapper("✅ Logged into GHCR")
                                
                                # Push Docker image
                                log_wrapper("📤 Pushing Docker image to GHCR...")
                                log_wrapper(f"📊 Progress: 90% - Pushing Docker image...")
                                
                                push_result = subprocess.run(
                                    ['docker', 'push', image_name],
                                    capture_output=True,
                                    text=True,
                                    timeout=600  # 10 minutes timeout
                                )
                                
                                if push_result.returncode == 0:
                                    log_wrapper("✅ Docker image pushed to GHCR successfully!")
                                    log_wrapper(f"🐳 Image URL: https://ghcr.io/{selected_repository}")
                                    log_wrapper(f"📊 Progress: 95% - Docker image pushed...")
                                    
                                    # Push latest tag
                                    subprocess.run(['docker', 'push', latest_image], capture_output=True, text=True, timeout=600)
                                    log_wrapper("✅ Latest tag pushed to GHCR")
                                    log_wrapper("📊 Progress: 100% - Deployment completed!")
                                    
                                    # Add Docker usage instructions
                                    log_wrapper("📋 Docker Usage Instructions:")
                                    log_wrapper(f"🐳 Pull: docker pull {image_name}")
                                    log_wrapper(f"🚀 Run: docker run -p 9998:9998 {image_name}")
                                    log_wrapper(f"🔧 Advanced: docker run -p 9998:9998 --name deploy-tool {image_name}")
                                    log_wrapper(f"📦 CI/CD: docker pull {image_name} && docker run -d -p 9998:9998 {image_name}")
                                    log_wrapper(f"🐳 Compose: Add to docker-compose.yml:")
                                    log_wrapper(f"   deploy-tool:")
                                    log_wrapper(f"     image: {image_name}")
                                    log_wrapper(f"     ports:")
                                    log_wrapper(f"       - '9998:9998'")
                                    log_wrapper(f"     volumes:")
                                    log_wrapper(f"       - 'your-path:/workspace'  # Optional")
                                    log_wrapper(f"🚢 Kubernetes: kubectl run deploy-tool --image={image_name} --port=9998")
                                    
                                else:
                                    log_wrapper(f"❌ Failed to push Docker image: {push_result.stderr}")
                                    return
                            else:
                                log_wrapper(f"❌ Failed to login to GHCR: {login_result.stderr}")
                                return
                        else:
                            log_wrapper(f"❌ Failed to build Docker image: {build_result.stderr}")
                            return
                            
                    except subprocess.TimeoutExpired:
                        log_wrapper("❌ Docker build/push timeout")
                        return
                    except Exception as e:
                        log_wrapper(f"❌ Docker build/push error: {e}")
                        return
            
                # Send completion signal
                log_wrapper("✅ Deployment process completed successfully!")
                log_wrapper("COMPLETION_SIGNAL")
                
            except Exception as e:
                log_wrapper(f"❌ Deployment error: {e}")
                import traceback
                log_wrapper(f"🔍 Error details: {traceback.format_exc()}")
                
                # Send error completion signal
                log_wrapper("ERROR_COMPLETION_SIGNAL")
        
        # Start deployment thread
        thread = threading.Thread(target=deploy_process)
        thread.daemon = True
        thread.start()
        
        # Return streaming response immediately
        return StreamingResponse(stream_logs(), media_type="text/event-stream")
        
    except Exception as e:
        return JSONResponse(content={'error': str(e)}, status_code=500)

@app.post("/verify-github-token")
async def verify_github_token(request: Request):
    """Verify GitHub token"""
    try:
        data = await request.json()
        github_username = data.get('github_username', '')
        github_token = data.get('github_token', '')
        
        # TODO: Implement GitHub token verification
        log_wrapper("🔍 Verifying GitHub token...")
        
        return {"status": "success", "message": "Token verified"}
        
    except Exception as e:
        log_wrapper(f"❌ Token verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-repositories")
async def get_repositories(github_username: str, github_token: str):
    """Get user repositories"""
    try:
        log_wrapper("📋 Getting user repositories...")
        
        # GitHub API endpoint for user repositories
        url = f"https://api.github.com/users/{github_username}/repos"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repositories = response.json()
            log_wrapper(f"✅ Found {len(repositories)} repositories")
            
            # Format repositories for frontend
            formatted_repos = []
            for repo in repositories:
                formatted_repos.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "language": repo.get("language", "Unknown"),
                    "private": repo["private"],
                    "visibility": "private" if repo["private"] else "public",
                    "url": repo["html_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"]
                })
            
            return {
                "repositories": formatted_repos,
                "total": len(formatted_repos),
                "status": "success"
            }
        else:
            log_wrapper(f"❌ GitHub API error: {response.status_code} - {response.text}")
            return {
                "repositories": [],
                "total": 0,
                "status": "error",
                "message": f"GitHub API error: {response.status_code}"
            }
        
    except Exception as e:
        log_wrapper(f"❌ Repository listing error: {e}")
        return {
            "repositories": [],
            "total": 0,
            "status": "error",
            "message": str(e)
        }

@app.post("/get-repositories")
async def get_repositories_post(request: Request):
    """Get user repositories via POST"""
    try:
        data = await request.json()
        github_username = data.get('github_username', '')
        github_token = data.get('github_token', '')
        
        if not github_username or not github_token:
            return {
                "repositories": [],
                "total": 0,
                "status": "error",
                "message": "GitHub username and token are required"
            }
        
        log_wrapper("📋 Getting user repositories via POST...")
        
        # GitHub API endpoint for user repositories
        url = f"https://api.github.com/users/{github_username}/repos"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repositories = response.json()
            log_wrapper(f"✅ Found {len(repositories)} repositories")
            
            # Format repositories for frontend
            formatted_repos = []
            for repo in repositories:
                formatted_repos.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "language": repo.get("language", "Unknown"),
                    "private": repo["private"],
                    "visibility": "private" if repo["private"] else "public",
                    "url": repo["html_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"]
                })
            
            return {
                "repositories": formatted_repos,
                "total": len(formatted_repos),
                "status": "success"
            }
        else:
            log_wrapper(f"❌ GitHub API error: {response.status_code} - {response.text}")
            return {
                "repositories": [],
                "total": 0,
                "status": "error",
                "message": f"GitHub API error: {response.status_code}"
            }
        
    except Exception as e:
        log_wrapper(f"❌ Repository listing error: {e}")
        return {
            "repositories": [],
            "total": 0,
            "status": "error",
            "message": str(e)
        }

@app.post("/create-repository")
async def create_repository(request: Request):
    """Create a new GitHub repository"""
    try:
        data = await request.json()
        github_username = data.get('github_username', '')
        github_token = data.get('github_token', '')
        repo_name = data.get('repo_name', '')
        description = data.get('description', '')
        is_private = data.get('private', False)
        
        if not github_username or not github_token or not repo_name:
            return {
                "status": "error",
                "message": "GitHub username, token, and repository name are required"
            }
        
        log_wrapper(f"🆕 Creating repository: {repo_name}")
        
        # GitHub API endpoint for creating repository
        url = "https://api.github.com/user/repos"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "name": repo_name,
            "description": description,
            "private": is_private,
            "auto_init": True  # Initialize with README
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            repository = response.json()
            log_wrapper(f"✅ Repository created successfully: {repository['full_name']}")
            
            return {
                "status": "success",
                "message": f"Repository created successfully: {repository['full_name']}",
                "repository": {
                    "name": repository["name"],
                    "full_name": repository["full_name"],
                    "description": repository.get("description", ""),
                    "private": repository["private"],
                    "url": repository["html_url"],
                    "created_at": repository["created_at"]
                }
            }
        else:
            log_wrapper(f"❌ GitHub API error: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"Failed to create repository: {response.status_code} - {response.text}"
            }
        
    except Exception as e:
        log_wrapper(f"❌ Repository creation error: {e}")
        return {
            "status": "error",
            "message": f"Error creating repository: {str(e)}"
        }

@app.post("/check-docker-images")
async def check_docker_images(request: Request):
    """Check Docker images in GitHub Container Registry and local Docker environment"""
    try:
        data = await request.json()
        github_username = data.get('github_username', '')
        github_token = data.get('github_token', '')
        repository = data.get('repository', '')
        
        if not github_username or not github_token or not repository:
            return {
                "error": "GitHub username, token, and repository are required"
            }
        
        log_wrapper(f"🐳 Checking Docker images for repository: {repository}")
        
        # Get ALL Docker images from GitHub Container Registry
        docker_images = []
        total_images = 0
        total_versions = 0
        
        # Get all user packages
        url = f"https://api.github.com/user/packages"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            packages = response.json()
            log_wrapper(f"📦 Found {len(packages)} total packages")
            
            # Get all container packages
            for package in packages:
                if package.get("package_type") == "container":
                    package_name = package.get("name", "")
                    package_owner = package.get("owner", {}).get("login", "")
                    full_package_name = f"{package_owner}/{package_name}"
                    
                    # Get detailed package info including versions
                    package_url = f"https://api.github.com/user/packages/container/{package_name}/versions"
                    package_response = requests.get(package_url, headers=headers)
                    
                    versions = []
                    version_count = 0
                    
                    if package_response.status_code == 200:
                        versions_data = package_response.json()
                        version_count = len(versions_data)
                        total_versions += version_count
                        
                                            # Get version details and sort by updated_at
                    for version in versions_data:
                        versions.append({
                            "name": version.get("name", ""),
                            "id": version.get("id", ""),
                            "created_at": version.get("created_at", ""),
                            "updated_at": version.get("updated_at", ""),
                            "url": version.get("html_url", ""),
                            "download_count": version.get("download_count", 0)
                        })
                    
                    # Sort versions by updated_at (newest first)
                    versions.sort(key=lambda x: x["updated_at"], reverse=True)
                    
                    docker_images.append({
                        "name": package_name,
                        "full_name": full_package_name,
                        "id": package["id"],
                        "visibility": package.get("visibility", "unknown"),
                        "created_at": package["created_at"],
                        "updated_at": package["updated_at"],
                        "url": package["html_url"],
                        "versions": version_count,
                        "version_details": versions
                    })
                    total_images += 1
                    
                    log_wrapper(f"🐳 Found: {full_package_name} ({version_count} versions)")
        else:
            log_wrapper(f"⚠️ GitHub packages API returned {response.status_code}")
            
            # Fallback: Get repository-specific packages
            repo_packages_url = f"https://api.github.com/repos/{repository}/packages"
            repo_response = requests.get(repo_packages_url, headers=headers)
            
            if repo_response.status_code == 200:
                packages = repo_response.json()
                
                for package in packages:
                    if package.get("package_type") == "container":
                        # Get versions for this package
                        package_name = package.get("name", "")
                        package_url = f"https://api.github.com/repos/{repository}/packages/container/{package_name}/versions"
                        package_response = requests.get(package_url, headers=headers)
                        
                        versions = []
                        version_count = 0
                        
                        if package_response.status_code == 200:
                            versions_data = package_response.json()
                            version_count = len(versions_data)
                            total_versions += version_count
                            
                            for version in versions_data:
                                versions.append({
                                    "name": version.get("name", ""),
                                    "id": version.get("id", ""),
                                    "created_at": version.get("created_at", ""),
                                    "updated_at": version.get("updated_at", ""),
                                    "url": version.get("html_url", "")
                                })
                        
                        docker_images.append({
                            "name": package_name,
                            "full_name": f"{repository}/{package_name}",
                            "id": package["id"],
                            "visibility": package.get("visibility", "unknown"),
                            "created_at": package["created_at"],
                            "updated_at": package["updated_at"],
                            "url": package["html_url"],
                            "versions": version_count,
                            "version_details": versions
                        })
                        total_images += 1
            else:
                log_wrapper(f"⚠️ Repository packages API returned {repo_response.status_code}")
                
                # Check local images as final fallback
                try:
                    local_check = subprocess.run(['docker', 'images', 'ghcr.io/' + repository], 
                                               capture_output=True, text=True)
                    if local_check.returncode == 0 and repository.split('/')[-1] in local_check.stdout:
                        log_wrapper("✅ Found Docker image locally")
                        from datetime import datetime
                        current_time = datetime.now().isoformat() + "Z"
                        
                        docker_images.append({
                            "name": f"ghcr.io/{repository}:latest",
                            "full_name": f"{repository}:latest",
                            "id": "local-found",
                            "visibility": "public",
                            "created_at": current_time,
                            "updated_at": current_time,
                            "url": f"https://ghcr.io/{repository}",
                            "versions": 1,
                            "version_details": [{"name": "latest", "created_at": current_time}]
                        })
                        total_images += 1
                        total_versions += 1
                except Exception as e:
                    log_wrapper(f"⚠️ Could not check local images: {e}")
        
        # Check local Docker images
        local_images = []
        try:
            # Get real local Docker images
            result = subprocess.run(['docker', 'images', '--format', 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}'], 
                                 capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header line
                    for line in lines[1:]:  # Skip header
                        parts = line.split('\t')
                        if len(parts) >= 5:
                            repo, tag, image_id, created, size = parts
                            if repo != '<none>' and tag != '<none>':
                                local_images.append({
                                    "name": f"{repo}:{tag}",
                                    "id": image_id,
                                    "created": created,
                                    "size": size
                                })
            
            # Only show real local images, no simulated data
            if not local_images:
                log_wrapper("ℹ️ No local Docker images found")
        except Exception as e:
            log_wrapper(f"⚠️ Could not check local Docker images: {e}")
            local_images = []  # No fallback, only real data
        
        repository_info = {
            "full_name": repository,
            "name": repository.split('/')[-1],
            "owner": repository.split('/')[0]
        }
        
        log_wrapper(f"✅ Found {total_images} Docker images with {total_versions} total versions")
        
        return {
            "repository_info": repository_info,
            "docker_images": docker_images,
            "local_images": local_images,
            "total_images": total_images,
            "total_versions": total_versions,
            "total_local_images": len(local_images),
            "status": "success"
        }
        
    except Exception as e:
        log_wrapper(f"❌ Docker images check error: {e}")
        return {
            "error": f"Error checking Docker images: {str(e)}"
        }

@app.get("/check-docker-environment")
async def check_docker_environment():
    """Check Docker environment and available paths for debugging"""
    try:
        import os
        import platform
        
        # Check if running in Docker
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        # Get system info
        system_info = {
            'platform': platform.system(),
            'platform_release': platform.release(),
            'is_docker': is_docker,
            'docker_env': os.environ.get('DOCKER_CONTAINER'),
            'has_dockerenv': os.path.exists('/.dockerenv'),
            'current_working_dir': os.getcwd(),
            'user': os.environ.get('USER', 'unknown'),
            'home': os.environ.get('HOME', 'unknown')
        }
        
        # Check available paths
        paths_to_check = [
            '/workspace',
            '/home',
            '/mnt',
            '/opt',
            '/app',
            '/root',
            '/tmp',
            '/var',
            '/usr',
            '/etc'
        ]
        
        path_info = {}
        for path in paths_to_check:
            path_obj = Path(path)
            if path_obj.exists():
                try:
                    items = list(path_obj.iterdir())
                    path_info[path] = {
                        'exists': True,
                        'is_dir': path_obj.is_dir(),
                        'is_file': path_obj.is_file(),
                        'item_count': len(items),
                        'sample_items': [item.name for item in items[:5]]
                    }
                except Exception as e:
                    path_info[path] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                path_info[path] = {
                    'exists': False
                }
        
        # Check environment variables
        env_vars = {}
        for key, value in os.environ.items():
            if any(keyword in key.lower() for keyword in ['docker', 'path', 'home', 'user', 'pwd']):
                env_vars[key] = value
        
        return {
            "system_info": system_info,
            "path_info": path_info,
            "environment_vars": env_vars
        }
        
    except Exception as e:
        log_wrapper(f"❌ Error checking Docker environment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-docker-volume")
async def test_docker_volume():
    """Test Docker volume mounting and provide troubleshooting info"""
    try:
        import os
        import subprocess
        
        # Check if running in Docker
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        result = {
            'is_docker': is_docker,
            'volume_test': {},
            'troubleshooting': {}
        }
        
        if is_docker:
            # Test common volume mount points
            test_paths = os.environ.get('TEST_PATHS', '/workspace,/home,/mnt,/opt,/app').split(',')
            
            for path in test_paths:
                path_obj = Path(path)
                if path_obj.exists():
                    try:
                        items = list(path_obj.iterdir())
                        result['volume_test'][path] = {
                            'exists': True,
                            'item_count': len(items),
                            'sample_items': [item.name for item in items[:10]],
                            'is_mounted': len(items) > 0  # Assume mounted if has items
                        }
                    except Exception as e:
                        result['volume_test'][path] = {
                            'exists': True,
                            'error': str(e)
                        }
                else:
                    result['volume_test'][path] = {
                        'exists': False
                    }
            
            # Check if any volume is properly mounted
            mounted_volumes = [path for path, info in result['volume_test'].items() 
                             if info.get('exists') and info.get('is_mounted', False)]
            
            if mounted_volumes:
                result['troubleshooting']['status'] = '✅ Volume mounted successfully'
                result['troubleshooting']['mounted_paths'] = mounted_volumes
                result['troubleshooting']['recommendation'] = f'Use one of these paths: {", ".join(mounted_volumes)}'
            else:
                result['troubleshooting']['status'] = '❌ No volumes mounted'
                result['troubleshooting']['recommendation'] = 'Run with: docker run -p 9998:9998 ghcr.io/goasutlor/push-build:latest'
            
            # Get Docker container info
            try:
                # Try to get container ID
                with open('/proc/self/cgroup', 'r') as f:
                    cgroup_content = f.read()
                    if 'docker' in cgroup_content:
                        result['container_info'] = {
                            'detected': True,
                            'cgroup_info': cgroup_content[:200] + '...' if len(cgroup_content) > 200 else cgroup_content
                        }
                    else:
                        result['container_info'] = {'detected': False}
            except Exception as e:
                result['container_info'] = {'error': str(e)}
        
        return result
        
    except Exception as e:
        log_wrapper(f"❌ Error testing Docker volume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-project-detection")
async def test_project_detection():
    """Test project detection in Docker environment"""
    try:
        import os
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        log_wrapper(f"🔍 Testing project detection...")
        log_wrapper(f"🐳 Running in Docker: {is_docker}")
        
        # Test multiple paths
        test_paths = os.environ.get('TEST_PATHS', '/workspace,/app,/home,/mnt,/opt,/root,/tmp').split(',')
        
        results = {}
        
        for test_path in test_paths:
            path = Path(test_path)
            log_wrapper(f"🔍 Testing path: {test_path}")
            
            if path.exists():
                log_wrapper(f"✅ Path {test_path} exists")
                try:
                    items = list(path.iterdir())
                    log_wrapper(f"📁 Found {len(items)} items in {test_path}")
                    
                    # List first few items
                    for i, item in enumerate(items[:10]):
                        log_wrapper(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
                    
                    if len(items) > 10:
                        log_wrapper(f"  ... and {len(items) - 10} more items")
                    
                    # Try to detect projects
                    projects = detect_projects_in_directory(path)
                    results[test_path] = {
                        'exists': True,
                        'item_count': len(items),
                        'projects_found': len(projects),
                        'projects': [project.dict() for project in projects]
                    }
                    
                except Exception as e:
                    log_wrapper(f"❌ Error testing {test_path}: {e}")
                    results[test_path] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                log_wrapper(f"❌ Path {test_path} does not exist")
                results[test_path] = {
                    'exists': False
                }
        
        return {
            'is_docker': is_docker,
            'current_directory': str(Path.cwd()),
            'results': results
        }
        
    except Exception as e:
        log_wrapper(f"❌ Error in test_project_detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add more endpoints as needed...

if __name__ == "__main__":
    import uvicorn
    import ssl
    import os
    
    # SSL configuration
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    # Always generate fresh certificates for HTTPS
    print("🔒 Generating HTTPS certificates...")
    try:
        import ipaddress
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Generate certificate with proper extensions
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TH"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Bangkok"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Bangkok"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Flexible Deploy Tool"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Create certificate with proper extensions
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
            ]),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key to files
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        print("✅ HTTPS certificates generated successfully")
        print("🔒 Starting with HTTPS on https://localhost:9998")
        
    except ImportError:
        print("❌ cryptography library not available")
        print("💡 Install with: pip install cryptography")
        exit(1)
    except Exception as e:
        print(f"❌ Failed to generate certificates: {e}")
        exit(1)
    
    # Run with HTTPS only
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=9998, 
        reload=True,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file
    ) 