#!/bin/bash

set -e  # Exit on error

echo "🚀 Building Enterprise Monitoring Platform Docker images..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Generate package-lock.json for frontend
echo -e "\n${YELLOW}Generating package-lock.json for frontend...${NC}"
cd frontend
if [ -f "generate-package-lock.sh" ]; then
    ./generate-package-lock.sh
else
    echo "Generating package-lock.json..."
    npm install --package-lock-only
fi
cd ..

# Build images
echo -e "\n${YELLOW}Building Docker images...${NC}"

# Build backend
echo -e "\n${YELLOW}Building backend image...${NC}"
docker build -t enterprise-monitoring-backend:latest ./backend

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backend image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build backend image${NC}"
    exit 1
fi

# Build frontend
echo -e "\n${YELLOW}Building frontend image...${NC}"
docker build -t enterprise-monitoring-frontend:latest ./frontend

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build frontend image${NC}"
    exit 1
fi

# List built images
echo -e "\n${YELLOW}Built Docker images:${NC}"
docker images | grep enterprise-monitoring

# Tag images for GitHub Container Registry (if needed)
if [ -n "$GITHUB_ACTIONS" ]; then
    echo -e "\n${YELLOW}Tagging images for GitHub Container Registry...${NC}"
    
    # Get registry from environment or use default
    REGISTRY=${REGISTRY:-ghcr.io}
    IMAGE_NAME=${IMAGE_NAME:-$GITHUB_REPOSITORY}
    
    docker tag enterprise-monitoring-backend:latest $REGISTRY/$IMAGE_NAME-backend:latest
    docker tag enterprise-monitoring-frontend:latest $REGISTRY/$IMAGE_NAME-frontend:latest
    
    echo -e "${GREEN}✅ Images tagged for GitHub Container Registry${NC}"
fi

echo -e "\n${GREEN}✅ All Docker images built successfully!${NC}"
echo -e "\n${YELLOW}To run the application:${NC}"
echo -e "  docker-compose up -d"
echo -e "\n${YELLOW}To view logs:${NC}"
echo -e "  docker-compose logs -f"
echo -e "\n${YELLOW}To stop:${NC}"
echo -e "  docker-compose down"
