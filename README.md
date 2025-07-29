# Flexible Deploy Tool

A universal deployment pipeline for any project with Docker-in-Docker support.

## 🚀 Quick Start

### Run with Docker (Recommended)

```bash
# Run with Docker-in-Docker support
docker run -d \
  --name deploy-tool \
  -p 9998:9998 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd):/workspace" \
  ghcr.io/goasutlor/push-build:latest
```

### Run with Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  deploy-tool:
    image: ghcr.io/goasutlor/push-build:latest
    container_name: deploy-tool
    ports:
      - "9998:9998"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./:/workspace
    environment:
      - DOCKER_CONTAINER=true
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d
```

## 🌐 Access the Application

Open your browser and go to:
- **HTTPS:** `https://localhost:9998`
- **HTTP:** `http://localhost:9998` (if HTTPS not available)

## 🔧 Features

### ✅ Full Docker-in-Docker Support
- **Build Docker Images:** From within the container
- **Push to GHCR:** Automatic push to GitHub Container Registry
- **Volume Mounting:** Access host filesystem
- **Continuous Deployment:** Run container 24/7

### ✅ Project Detection
- **Auto Scan:** Detects projects in mounted volumes
- **Multiple Types:** Flask, Node.js, Java, Rust, Go, Docker
- **Git Integration:** Detects Git repositories

### ✅ GitHub Integration
- **Repository Management:** Create and manage repositories
- **Token Authentication:** Secure GitHub token handling
- **Auto Push:** Push code to GitHub automatically

### ✅ Docker Image Management
- **Build Images:** Build Docker images automatically
- **Push to GHCR:** Push to GitHub Container Registry
- **Version Tagging:** Automatic version management
- **Usage Instructions:** Generate Docker run commands

## 📋 Prerequisites

- Docker Desktop installed and running
- GitHub Personal Access Token with `repo` and `write:packages` permissions

## 🔐 GitHub Setup

1. **Create Personal Access Token:**
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token with `repo` and `write:packages` permissions

2. **Configure Repository:**
   - Create a repository on GitHub
   - Note the repository name (e.g., `username/repo-name`)

## 🔄 Usage Workflow

1. **Start the Container:**
   ```bash
   docker run -d --name deploy-tool -p 9998:9998 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v "$(pwd):/workspace" \
     ghcr.io/goasutlor/push-build:latest
   ```

2. **Access the Web Interface:**
   - Open `https://localhost:9998`
   - Navigate to the "Scan Projects" tab

3. **Configure GitHub:**
   - Go to "GitHub" tab
   - Enter your GitHub username and token
   - Load your repositories

4. **Deploy Projects:**
   - Go to "Deploy" tab
   - Select project and repository
   - Click "Deploy"
   - Watch real-time logs

5. **Monitor Docker Images:**
   - Go to "Docker Images" tab
   - View all images in GitHub Container Registry
   - Copy pull commands

## 🛠️ Troubleshooting

### Docker Socket Issues
```bash
# Check if Docker socket is accessible
ls -la /var/run/docker.sock

# Fix permissions if needed
sudo chmod 666 /var/run/docker.sock
```

### Volume Mounting Issues
```bash
# Check if volume is mounted correctly
docker exec deploy-tool ls -la /workspace

# Recreate container with correct volume
docker stop deploy-tool
docker rm deploy-tool
docker run -d --name deploy-tool -p 9998:9998 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd):/workspace" \
  ghcr.io/goasutlor/push-build:latest
```

### GitHub Authentication Issues
- Verify your GitHub token has correct permissions
- Check if token is not expired
- Ensure repository exists and is accessible

## 🔒 Security Considerations

- **HTTPS Only:** Application runs on HTTPS by default
- **Token Security:** GitHub tokens are handled securely
- **Container Isolation:** Runs in isolated container
- **Volume Permissions:** Proper file permissions

## 📊 Monitoring

### Health Check
```bash
# Check container health
docker ps

# View logs
docker logs deploy-tool

# Check application health
curl https://localhost:9998/health
```

### Docker Environment Check
- Use the "Check Docker" button in the web interface
- Verify Docker socket accessibility
- Check volume mounting status

## 🚀 Advanced Usage

### Production Deployment
```bash
# Run with production settings
docker run -d \
  --name deploy-tool-prod \
  -p 9998:9998 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/projects:/workspace \
  -e DOCKER_CONTAINER=true \
  --restart unless-stopped \
  ghcr.io/goasutlor/push-build:latest
```

### Multi-User Setup
```bash
# Run multiple instances on different ports
docker run -d --name deploy-tool-1 -p 9998:9998 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /path/to/projects1:/workspace \
  ghcr.io/goasutlor/push-build:latest

docker run -d --name deploy-tool-2 -p 9999:9998 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /path/to/projects2:/workspace \
  ghcr.io/goasutlor/push-build:latest
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details 