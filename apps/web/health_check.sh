#!/bin/bash

# Frontend Health Check Script
# This script monitors the frontend and restarts it if needed

set -e

# Configuration
PORT=${PORT:-3000}
HEALTH_CHECK_INTERVAL=30
MAX_FAILURES=3
LOG_FILE="/tmp/frontend_health.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if frontend is healthy
check_frontend_health() {
    # Check if port is listening
    if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if frontend responds to HTTP request
    if curl -s -f "http://localhost:$PORT" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to restart frontend
restart_frontend() {
    log "${YELLOW}Frontend is unhealthy, attempting restart...${NC}"
    
    # Kill existing frontend process
    if [ -f "/tmp/frontend.pid" ]; then
        local pid=$(cat /tmp/frontend.pid)
        if kill -0 $pid 2>/dev/null; then
            log "${YELLOW}Killing existing frontend process (PID: $pid)${NC}"
            kill -9 $pid 2>/dev/null || true
        fi
        rm -f /tmp/frontend.pid
    fi
    
    # Kill any process on the port
    if lsof -ti:$PORT >/dev/null 2>&1; then
        lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    fi
    
    # Wait a moment
    sleep 2
    
    # Start frontend using gpucloud management script
    cd /home/paperspace/NewMyPods/mypods
    ./gpucloud.sh rebuild > /tmp/frontend_restart.log 2>&1 &
    
    log "${GREEN}Frontend restart initiated${NC}"
}

# Main health check loop
main() {
    log "${GREEN}Frontend Health Check Started${NC}"
    log "${GREEN}Port: $PORT${NC}"
    log "${GREEN}Check Interval: ${HEALTH_CHECK_INTERVAL}s${NC}"
    log "${GREEN}Max Failures: $MAX_FAILURES${NC}"
    
    local failure_count=0
    
    while true; do
        if check_frontend_health; then
            if [ $failure_count -gt 0 ]; then
                log "${GREEN}Frontend is healthy again${NC}"
                failure_count=0
            fi
            log "${GREEN}Frontend health check passed${NC}"
        else
            failure_count=$((failure_count + 1))
            log "${YELLOW}Frontend health check failed (attempt $failure_count/$MAX_FAILURES)${NC}"
            
            if [ $failure_count -ge $MAX_FAILURES ]; then
                log "${RED}Maximum failures reached, restarting frontend${NC}"
                restart_frontend
                failure_count=0
                # Wait longer after restart
                sleep 60
            fi
        fi
        
        sleep $HEALTH_CHECK_INTERVAL
    done
}

# Handle shutdown
cleanup() {
    log "${YELLOW}Health check shutting down...${NC}"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Run main function
main
