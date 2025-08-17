#!/bin/bash
# GPUCloud Service Management Script
# Usage: ./gpucloud.sh {start|stop|restart|status|logs}

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/paperspace/mypods"
VENV_PATH="$PROJECT_ROOT/venv"
API_PORT=8080
FRONTEND_PORT=3000
REDIS_PORT=6379
POSTGRES_PORT=5432

# Service names for easy identification
SERVICE_NAME="gpucloud"
API_SERVICE="uvicorn.*apps.api.app.main:app"
WORKER_SERVICE="python.*apps.api.workers"
FRONTEND_SERVICE="next-server"
HEALTH_SERVICE="python.*health_checker"
REDIS_SERVICE="redis-server"
POSTGRES_SERVICE="postgres"

# Function to log with timestamp
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Function to check if a port is listening
is_port_listening() {
    ss -tuln 2>/dev/null | grep -q ":$1 "
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name="$1"
    local port="$2"
    local max_attempts=30
    local attempt=1
    
    log "Waiting for $service_name to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if is_port_listening $port; then
            log "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "${RED}❌ $service_name failed to start after $max_attempts attempts${NC}"
    return 1
}

# Function to start database services
start_database() {
    log "🗄️  Starting database services..."
    
    if ! is_running "postgres"; then
        docker compose up -d postgres redis
        log "✅ Database services started"
    else
        log "✅ Database services already running"
    fi
    
    # Wait for Redis
    wait_for_service "Redis" $REDIS_PORT
    
    # Wait for PostgreSQL
    wait_for_service "PostgreSQL" $POSTGRES_PORT
}

# Function to start API server
start_api() {
    log "🌐 Starting FastAPI server..."
    
    if ! is_running "$API_SERVICE"; then
        cd "$PROJECT_ROOT"
        source "$VENV_PATH/bin/activate"
        export PYTHONPATH="$PROJECT_ROOT"
        
        # Start API server in background with timestamped logging
        uvicorn apps.api.app.main:app --host 0.0.0.0 --port $API_PORT --access-log --log-level info 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"; done > /tmp/gpucloud_api.log &
        API_PID=$!
        echo $API_PID > /tmp/gpucloud_api.pid
        
        log "✅ API server started (PID: $API_PID)"
    else
        log "✅ API server already running"
    fi
    
    # Wait for API to be ready
    wait_for_service "FastAPI" $API_PORT
}

# Function to start worker
start_worker() {
    log "👷 Starting RQ worker..."
    
    if ! is_running "$WORKER_SERVICE"; then
        cd "$PROJECT_ROOT"
        source "$VENV_PATH/bin/activate"
        export PYTHONPATH="$PROJECT_ROOT"
        
        # Start worker in background with timestamped logging
        python -m apps.api.workers 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"; done > /tmp/gpucloud_worker.log &
        WORKER_PID=$!
        echo $WORKER_PID > /tmp/gpucloud_worker.pid
        
        log "✅ Worker started (PID: $WORKER_PID)"
    else
        log "✅ Worker already running"
    fi
}

# Function to start nginx
start_nginx() {
    log "🔒 Starting nginx..."
    
    if ! systemctl is-active --quiet nginx; then
        sudo systemctl start nginx
        log "✅ Nginx started"
    else
        log "✅ Nginx already running"
    fi
}

# Function to build frontend (clean build)
build_frontend() {
    log "🔨 Building frontend (clean build)..."
    cd "$PROJECT_ROOT/apps/web"
    
    # Remove old build files to ensure clean build
    if [ -d ".next" ]; then
        log "🧹 Removing old build files..."
        rm -rf .next
    fi
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log "📦 Installing Node.js dependencies..."
        npm install
    fi
    
    # Build the frontend
    log "🏗️  Building Next.js application..."
    if npm run build; then
        log "✅ Frontend build completed successfully"
        return 0
    else
        log "${RED}❌ Frontend build failed${NC}"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    log "🎨 Starting frontend on localhost only..."
    
    # Always build frontend first to ensure clean build
    if ! build_frontend; then
        log "${RED}❌ Failed to build frontend, cannot start${NC}"
        return 1
    fi
    
    if ! is_port_listening 3000; then
        cd "$PROJECT_ROOT/apps/web"
        
        # Start Next.js server on localhost only (127.0.0.1) to prevent external access
        # This ensures only Nginx can proxy to it
        npx next start --hostname 127.0.0.1 > /tmp/gpucloud_frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > /tmp/gpucloud_frontend.pid
        
        # Wait for frontend to be ready
        wait_for_service "Frontend" 3000
        
        log "✅ Frontend started on localhost only (PID: $FRONTEND_PID)"
    else
        log "✅ Frontend already running on localhost"
        # Get PID from existing process
        FRONTEND_PID=$(ss -tlnp | grep :3000 | awk '{print $7}' | cut -d',' -f1 | cut -d'(' -f2)
        echo $FRONTEND_PID > /tmp/gpucloud_frontend.pid
    fi
}

# Function to start health monitoring
start_health_monitoring() {
    log "🏥 Starting health monitoring..."
    
    if ! is_running "$HEALTH_SERVICE"; then
        cd "$PROJECT_ROOT"
        source "$VENV_PATH/bin/activate"
        export PYTHONPATH="$PROJECT_ROOT"
        
        # Start health monitoring in background with proper process management
        python -c "
import time
import signal
import sys
from apps.api.app.health_checker import start_health_monitoring

def signal_handler(signum, frame):
    print('Health monitoring received signal, shutting down...')
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

print('Health monitoring started')
start_health_monitoring()

# Keep the main thread alive
while True:
    time.sleep(1)
" > /tmp/gpucloud_health.log 2>&1 &
        HEALTH_PID=$!
        echo $HEALTH_PID > /tmp/gpucloud_health.pid
        
        log "✅ Health monitoring started (PID: $HEALTH_PID)"
    else
        log "✅ Health monitoring already running"
    fi
}

# Function to start all services
start_all() {
    log "${GREEN}🚀 Starting GPUCloud Production System...${NC}"
    
    # Check prerequisites
    if [ ! -d "$VENV_PATH" ]; then
        log "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
        exit 1
    fi
    
    # Start services in order
    start_database
    start_nginx
    start_health_monitoring
    start_worker
    start_api
    start_frontend
    
    # Display status
    log "${GREEN}🎉 GPUCloud Production System Started Successfully!${NC}"
    echo ""
    echo "📊 Service Status:"
    echo "  🗄️  Database Services: ${GREEN}Running${NC}"
    echo "  🏥 Health Monitoring: ${GREEN}Running${NC}"
    echo "  👷 RQ Worker: ${GREEN}Running${NC}"
    echo "  🌐 FastAPI Server: ${GREEN}Running${NC}"
    echo "  🎨 Frontend: ${GREEN}Running${NC}"
    echo "  🔒 Nginx (SSL): ${GREEN}Running${NC}"
    echo ""
    echo "🌐 Access URLs:"
    echo "  Frontend Dashboard: http://184.105.5.179 (via nginx)"
    echo "  Backend API: http://184.105.5.179/v1/ (via nginx)"
    echo "  API Health: http://184.105.5.179/v1/health (via nginx)"
    echo "  API Docs: http://184.105.5.179/docs (via nginx)"
    echo "  Note: Frontend runs on localhost:3000 (Nginx proxy only)"
    echo ""
    echo "📋 Management Commands:"
    echo "  Status: ./gpucloud.sh status"
    echo "  Stop: ./gpucloud.sh stop"
    echo "  Restart: ./gpucloud.sh restart"
    echo "  Logs: ./gpucloud.sh logs"
}

# Function to stop a service
stop_service() {
    local service_name="$1"
    local pid_file="$2"
    local process_pattern="$3"
    
    # First try to stop using PID file if it exists
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log "Stopping $service_name (PID: $pid)..."
            kill "$pid"
            rm -f "$pid_file"
            log "✅ $service_name stopped"
            return 0
        else
            log "PID file exists but process not running, cleaning up..."
            rm -f "$pid_file"
        fi
    fi
    
    # If no PID file or process not found, check if it's running by pattern
    if [ -n "$process_pattern" ] && is_running "$process_pattern"; then
        log "Found running $service_name process, stopping it..."
        pkill -f "$process_pattern"
        log "✅ $service_name stopped"
    else
        log "✅ $service_name already stopped"
    fi
}

# Function to stop all services
stop_all() {
    log "${YELLOW}🛑 Stopping GPUCloud Production System...${NC}"
    
    # Stop services
    stop_service "Frontend" "/tmp/gpucloud_frontend.pid" "next dev"
    stop_service "API Server" "/tmp/gpucloud_api.pid" "uvicorn apps.api.app.main:app"
    stop_service "Worker" "/tmp/gpucloud_worker.pid" "python -m apps.api.workers"
    stop_service "Health Monitoring" "/tmp/gpucloud_health.pid" "$HEALTH_SERVICE"
    
    # Stop database services
    log "🗄️  Stopping database services..."
    docker compose down
    log "✅ Database services stopped"
    
    # Stop nginx if running
    if systemctl is-active --quiet nginx; then
        log "🔒 Stopping nginx..."
        sudo systemctl stop nginx
        log "✅ Nginx stopped"
    fi
    
    log "${GREEN}✅ All services stopped${NC}"
}

# Function to show service status
show_status() {
    log "${PURPLE}📊 GPUCloud Service Status${NC}"
    echo ""
    
    # Check each service
    local all_running=true
    
    echo "🔒 Nginx (SSL):"
    if systemctl is-active --quiet nginx; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo "🗄️  Database Services:"
    if is_running "postgres" && is_running "redis"; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo "🏥 Health Monitoring:"
    if is_running "$HEALTH_SERVICE"; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo "👷 RQ Worker:"
    if is_running "$WORKER_SERVICE"; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo "🌐 FastAPI Server:"
    if is_running "$API_SERVICE"; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo "🎨 Frontend:"
    if is_port_listening $FRONTEND_PORT; then
        echo "  ${GREEN}✅ Running${NC}"
    else
        echo "  ${RED}❌ Stopped${NC}"
        all_running=false
    fi
    
    echo ""
    if [ "$all_running" = true ]; then
        echo "${GREEN}🎉 All services are running!${NC}"
        echo ""
        echo "🌐 Access URLs:"
        echo "  Frontend: https://184.105.5.179"
        echo "  API: https://184.105.5.179/v1/"
        echo "  Health: https://184.105.5.179/health"
    else
        echo "${YELLOW}⚠️  Some services are not running${NC}"
        echo "Use './gpucloud.sh start' to start all services"
    fi
}

# Function to show logs
show_logs() {
    log "${PURPLE}📋 GPUCloud Service Logs${NC}"
    echo ""
    echo "Select log to view:"
    echo "1) API Server logs"
    echo "2) Worker logs"
    echo "3) Frontend logs"
    echo "4) Health monitoring logs"
    echo "5) Nginx access logs"
    echo "6) Nginx error logs"
    echo "7) All logs (tail -f)"
    echo ""
    read -p "Enter choice (1-7): " choice
    
    case $choice in
        1) tail -f /tmp/gpucloud_api.log ;;
        2) tail -f /tmp/gpucloud_worker.log ;;
        3) tail -f /tmp/gpucloud_frontend.log ;;
        4) tail -f /tmp/gpucloud_health.log ;;
        5) sudo tail -f /var/log/nginx/gpucloud_access.log ;;
        6) sudo tail -f /var/log/nginx/gpucloud_error.log ;;
        7) 
            echo "Showing all logs (Ctrl+C to stop)..."
            tail -f /tmp/gpucloud_*.log /var/log/nginx/gpucloud_*.log 2>/dev/null || true
            ;;
        *) echo "Invalid choice" ;;
    esac
}

# Function to restart all services
restart_all() {
    log "${YELLOW}🔄 Restarting GPUCloud Production System...${NC}"
    stop_all
    sleep 2
    start_all
}

# Function to rebuild frontend only
rebuild_frontend() {
    log "${YELLOW}🔄 Rebuilding frontend only...${NC}"
    
    # Stop frontend if running
    if is_port_listening 3000; then
        log "🛑 Stopping frontend for rebuild..."
        stop_service "Frontend" "/tmp/gpucloud_frontend.pid" "next"
        sleep 2
    fi
    
    # Build and start frontend
    if start_frontend; then
        log "${GREEN}✅ Frontend rebuilt and started successfully${NC}"
    else
        log "${RED}❌ Frontend rebuild failed${NC}"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "GPUCloud Service Management Script"
    echo ""
    echo "Usage: ./gpucloud.sh {start|stop|restart|rebuild|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start   - Start all GPUCloud services"
    echo "  stop    - Stop all GPUCloud services"
    echo "  restart - Restart all GPUCloud services"
    echo "  rebuild - Rebuild and restart frontend only"
    echo "  status  - Show status of all services"
    echo "  logs    - Show service logs"
    echo "  help    - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./gpucloud.sh start    # Start all services"
    echo "  ./gpucloud.sh rebuild  # Rebuild frontend only"
    echo "  ./gpucloud.sh status   # Check service status"
    echo "  ./gpucloud.sh logs     # View service logs"
}

# Main script logic
case "${1:-help}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    rebuild)
        rebuild_frontend
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|*)
        show_help
        ;;
esac
