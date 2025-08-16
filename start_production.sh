#!/bin/bash
# GPUCloud Production Startup Script with Comprehensive Safeguards

set -e  # Exit on any error

echo "🚀 Starting GPUCloud Production System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/paperspace/mypods"
VENV_PATH="$PROJECT_ROOT/venv"
API_PORT=8080
WORKER_QUEUE="provision"
REDIS_URL="redis://localhost:6379"

# Function to log with timestamp
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name="$1"
    local port="$2"
    local max_attempts=30
    local attempt=1
    
    log "Waiting for $service_name to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
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

# Function to start service with retry
start_service() {
    local service_name="$1"
    local start_cmd="$2"
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        log "Starting $service_name (attempt $((retry + 1))/$max_retries)..."
        
        if eval "$start_cmd"; then
            log "${GREEN}✅ $service_name started successfully${NC}"
            return 0
        else
            retry=$((retry + 1))
            log "${YELLOW}⚠️  Failed to start $service_name, attempt $retry/$max_retries${NC}"
            
            if [ $retry -lt $max_retries ]; then
                sleep 5
            fi
        fi
    done
    
    log "${RED}❌ Failed to start $service_name after $max_retries attempts${NC}"
    return 1
}

# Function to cleanup on exit
cleanup() {
    log "🛑 Shutting down GPUCloud services..."
    
    # Stop all background processes
    pkill -f "uvicorn.*apps.api.app.main:app" || true
    pkill -f "python.*apps.api.workers" || true
    pkill -f "rq worker" || true
    pkill -f "next dev" || true
    
    log "✅ Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check prerequisites
log "🔍 Checking prerequisites..."

if [ ! -d "$VENV_PATH" ]; then
    log "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log "${RED}❌ Docker not found${NC}"
    exit 1
fi

if ! command -v redis-server &> /dev/null; then
    log "${YELLOW}⚠️  Redis server not found, will use Docker Redis${NC}"
fi

# Start database services
log "🗄️  Starting database services..."
if ! is_running "postgres"; then
    docker compose up -d postgres redis
    log "✅ Database services started"
else
    log "✅ Database services already running"
fi

# Wait for Redis to be ready
wait_for_service "Redis" 6379

# Activate virtual environment
log "🐍 Activating virtual environment..."
source "$VENV_PATH/bin/activate"
export PYTHONPATH="$PROJECT_ROOT"

# Start health monitoring
log "🏥 Starting health monitoring system..."
python -c "
from apps.api.app.health_checker import start_health_monitoring
start_health_monitoring()
print('Health monitoring started')
" &
HEALTH_PID=$!

# Start RQ worker with enhanced monitoring
log "👷 Starting enhanced RQ worker..."
cd "$PROJECT_ROOT"
python -m apps.api.workers &
WORKER_PID=$!

# Wait for worker to be ready
sleep 5
if ! is_running "apps.api.workers"; then
    log "${RED}❌ Worker failed to start${NC}"
    exit 1
fi

# Start FastAPI server
log "🌐 Starting FastAPI server..."
cd "$PROJECT_ROOT"
uvicorn apps.api.app.main:app --host 0.0.0.0 --port $API_PORT &
API_PID=$!

# Wait for API to be ready
wait_for_service "FastAPI" $API_PORT

# Start frontend
log "🎨 Starting frontend..."
cd "$PROJECT_ROOT/apps/web"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to be ready
wait_for_service "Frontend" 3000

# Display status
log "${GREEN}🎉 GPUCloud Production System Started Successfully!${NC}"
echo ""
echo "📊 Service Status:"
echo "  🗄️  Database Services: ${GREEN}Running${NC}"
echo "  🏥 Health Monitoring: ${GREEN}Running${NC} (PID: $HEALTH_PID)"
echo "  👷 RQ Worker: ${GREEN}Running${NC} (PID: $WORKER_PID)"
echo "  🌐 FastAPI Server: ${GREEN}Running${NC} (PID: $API_PID)"
echo "  🎨 Frontend: ${GREEN}Running${NC} (PID: $FRONTEND_PID)"
echo ""
echo "🌐 Access URLs:"
echo "  Frontend Dashboard: http://184.105.5.179:3000"
echo "  Backend API: http://184.105.5.179:$API_PORT"
echo "  API Health: http://184.105.5.179:$API_PORT/v1/health"
echo "  API Docs: http://184.105.5.179:$API_PORT/docs"
echo ""
echo "📋 Monitoring Commands:"
echo "  Check system health: curl http://184.105.5.179:$API_PORT/v1/health"
echo "  Check worker status: source $VENV_PATH/bin/activate && rq info --url $REDIS_URL"
echo "  View logs: tail -f /var/log/gpucloud/*.log"
echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Monitor services and restart if needed
while true; do
    sleep 30
    
    # Check if any service died
    if ! is_running "apps.api.workers"; then
        log "${YELLOW}⚠️  Worker died, restarting...${NC}"
        cd "$PROJECT_ROOT"
        python -m apps.api.workers &
        WORKER_PID=$!
    fi
    
    if ! is_running "uvicorn.*apps.api.app.main:app"; then
        log "${YELLOW}⚠️  API server died, restarting...${NC}"
        cd "$PROJECT_ROOT"
        uvicorn apps.api.app.main:app --host 0.0.0.0 --port $API_PORT &
        API_PID=$!
    fi
    
    if ! is_running "next dev"; then
        log "${YELLOW}⚠️  Frontend died, restarting...${NC}"
        cd "$PROJECT_ROOT/apps/web"
        npm run dev &
        FRONTEND_PID=$!
    fi
    
    # Log health status
    if [ $((SECONDS % 300)) -eq 0 ]; then  # Every 5 minutes
        log "💓 System heartbeat - all services running"
    fi
done
