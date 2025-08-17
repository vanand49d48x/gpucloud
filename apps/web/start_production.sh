#!/bin/bash

# Production Frontend Startup Script
# This script starts the Next.js frontend with auto-restart capabilities

set -e

# Configuration
PORT=${PORT:-3000}
HOST=${HOST:-0.0.0.0}
MAX_RESTARTS=10
RESTART_DELAY=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if port is in use
check_port() {
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to build frontend (clean build)
build_frontend() {
    log "${GREEN}Building Next.js frontend (clean build)...${NC}"
    cd "$(dirname "$0")"
    
    # Remove old build files to ensure clean build
    if [ -d ".next" ]; then
        log "${YELLOW}Removing old build files for clean build...${NC}"
        rm -rf .next
    fi
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log "${GREEN}Installing Node.js dependencies...${NC}"
        npm install
    fi
    
    # Build the frontend
    log "${GREEN}Building Next.js application...${NC}"
    if npm run build; then
        log "${GREEN}Frontend build completed successfully${NC}"
        return 0
    else
        log "${RED}Frontend build failed${NC}"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    log "${GREEN}Starting Next.js frontend on port $PORT...${NC}"
    
    # Kill any existing process on the port
    if check_port; then
        log "${YELLOW}Port $PORT is in use, killing existing process...${NC}"
        lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # Always build frontend first to ensure clean build
    if ! build_frontend; then
        log "${RED}Failed to build frontend, cannot start${NC}"
        return 1
    fi
    
    # Start the frontend
    cd "$(dirname "$0")"
    
    # Use production build (we just built it)
    log "${GREEN}Using fresh production build${NC}"
    npm start &
    
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/frontend.pid
    
    log "${GREEN}Frontend started with PID: $FRONTEND_PID${NC}"
    
    # Wait for frontend to be ready
    local attempts=0
    local max_attempts=30
    
    while [ $attempts -lt $max_attempts ]; do
        if check_port; then
            log "${GREEN}Frontend is ready on port $PORT${NC}"
            return 0
        fi
        
        attempts=$((attempts + 1))
        log "${YELLOW}Waiting for frontend to be ready... (attempt $attempts/$max_attempts)${NC}"
        sleep 2
    done
    
    log "${RED}Frontend failed to start within expected time${NC}"
    return 1
}

# Function to monitor and restart frontend
monitor_frontend() {
    local restart_count=0
    
    while [ $restart_count -lt $MAX_RESTARTS ]; do
        if ! check_port; then
            log "${YELLOW}Frontend is not responding, attempting restart...${NC}"
            
            # Kill existing process
            if [ -f "/tmp/frontend.pid" ]; then
                local pid=$(cat /tmp/frontend.pid)
                if kill -0 $pid 2>/dev/null; then
                    log "${YELLOW}Killing existing frontend process (PID: $pid)${NC}"
                    kill -9 $pid 2>/dev/null || true
                fi
            fi
            
            # Wait before restart
            log "${YELLOW}Waiting $RESTART_DELAY seconds before restart...${NC}"
            sleep $RESTART_DELAY
            
            # Restart
            if start_frontend; then
                restart_count=0
                log "${GREEN}Frontend restarted successfully${NC}"
            else
                restart_count=$((restart_count + 1))
                log "${RED}Frontend restart failed (attempt $restart_count/$MAX_RESTARTS)${NC}"
            fi
        else
            # Frontend is running, reset restart count
            restart_count=0
            sleep 10
        fi
    done
    
    log "${RED}Maximum restart attempts reached. Frontend is not responding.${NC}"
    exit 1
}

# Function to handle shutdown
cleanup() {
    log "${YELLOW}Shutting down frontend...${NC}"
    
    if [ -f "/tmp/frontend.pid" ]; then
        local pid=$(cat /tmp/frontend.pid)
        if kill -0 $pid 2>/dev/null; then
            kill -TERM $pid 2>/dev/null
            sleep 2
            kill -9 $pid 2>/dev/null || true
        fi
        rm -f /tmp/frontend.pid
    fi
    
    # Kill any process on the port
    if check_port; then
        lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    fi
    
    log "${GREEN}Frontend shutdown complete${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Main execution
log "${GREEN}GPUCloud Frontend Production Startup Script${NC}"
log "${GREEN}Port: $PORT${NC}"
log "${GREEN}Host: $HOST${NC}"
log "${GREEN}Max Restarts: $MAX_RESTARTS${NC}"

# Start frontend initially
if start_frontend; then
    log "${GREEN}Frontend started successfully, beginning monitoring...${NC}"
    monitor_frontend
else
    log "${RED}Failed to start frontend initially${NC}"
    exit 1
fi
