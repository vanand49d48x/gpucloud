from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import os
import glob
import json
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/logs", tags=["logs"])

class LogEntry:
    def __init__(self, timestamp: str, level: str, message: str, data: dict = None, app: str = None, source: str = None):
        self.timestamp = timestamp
        self.level = level
        self.message = message
        self.data = data or {}
        self.app = app
        self.source = source

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "data": self.data,
            "app": self.app,
            "source": self.source
        }

@router.get("/")
async def get_all_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    search: Optional[str] = Query(None, description="Search in log messages"),
    limit: int = Query(1000, description="Maximum number of logs to return"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter logs since"),
    app: Optional[str] = Query(None, description="Filter by specific app")
):
    """Get logs from all applications with optional filtering"""
    try:
        logs = await collect_logs_from_all_apps()
        
        # Apply filters
        if level:
            logs = [log for log in logs if log.level.upper() == level.upper()]
        
        if search:
            search_lower = search.lower()
            logs = [log for log in logs if search_lower in log.message.lower()]
        
        if since:
            try:
                since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
                logs = [log for log in logs if datetime.fromisoformat(log.timestamp) >= since_time]
            except ValueError:
                logger.warning(f"Invalid since timestamp: {since}")
        
        if app:
            logs = [log for log in logs if log.app and app.lower() in log.app.lower()]
        
        # Limit results
        logs = logs[-limit:] if limit > 0 else logs
        
        return {
            "logs": [log.to_dict() for log in logs],
            "total": len(logs),
            "filtered": len(logs),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting all logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@router.get("/{app_name}")
async def get_app_logs(
    app_name: str,
    level: Optional[str] = Query(None, description="Filter by log level"),
    search: Optional[str] = Query(None, description="Search in log messages"),
    limit: int = Query(1000, description="Maximum number of logs to return"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter logs since"),
    follow: bool = Query(False, description="Follow logs in real-time (for WebSocket)")
):
    """Get logs from a specific application"""
    try:
        logs = await collect_logs_from_app(app_name)
        
        # Apply filters
        if level:
            logs = [log for log in logs if log.level.upper() == level.upper()]
        
        if search:
            search_lower = search.lower()
            logs = [log for log in logs if search_lower in log.message.lower()]
        
        if since:
            try:
                since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
                logs = [log for log in logs if datetime.fromisoformat(log.timestamp) >= since_time]
            except ValueError:
                logger.warning(f"Invalid since timestamp: {since}")
        
        # Limit results
        logs = logs[-limit:] if limit > 0 else logs
        
        return {
            "logs": [log.to_dict() for log in logs],
            "total": len(logs),
            "filtered": len(logs),
            "app": app_name,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting logs for app {app_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@router.get("/{app_name}/tail")
async def tail_app_logs(
    app_name: str,
    lines: int = Query(100, description="Number of lines to return"),
    follow: bool = Query(False, description="Follow logs in real-time")
):
    """Get the last N lines from a specific application (like tail -f)"""
    try:
        logs = await collect_logs_from_app(app_name)
        tail_logs = logs[-lines:] if lines > 0 else logs
        
        return {
            "logs": [log.to_dict() for log in tail_logs],
            "total": len(tail_logs),
            "app": app_name,
            "following": follow,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error tailing logs for app {app_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to tail logs: {str(e)}")

async def collect_logs_from_all_apps() -> List[LogEntry]:
    """Collect logs from all known applications"""
    all_logs = []
    
    # Known app directories
    app_dirs = [
        ("frontend", "apps/web"),
        ("backend", "apps/api"),
        ("nginx", "/var/log/nginx"),
        ("system", "/var/log")
    ]
    
    for app_name, app_path in app_dirs:
        try:
            app_logs = await collect_logs_from_app(app_name, app_path)
            all_logs.extend(app_logs)
        except Exception as e:
            logger.warning(f"Failed to collect logs from {app_name}: {e}")
    
    # Sort by timestamp
    all_logs.sort(key=lambda x: x.timestamp)
    return all_logs

async def collect_logs_from_app(app_name: str, app_path: str = None) -> List[LogEntry]:
    """Collect logs from a specific application"""
    logs = []
    
    if not app_path:
        # Default paths for known apps
        app_paths = {
            "frontend": "apps/web",
            "backend": "apps/api",
            "nginx": "/var/log/nginx",
            "system": "/var/log"
        }
        app_path = app_paths.get(app_name, app_name)
    
    try:
        if app_name == "frontend":
            logs.extend(await collect_frontend_logs())
        elif app_name == "backend":
            logs.extend(await collect_backend_logs())
        elif app_name == "nginx":
            logs.extend(await collect_nginx_logs())
        elif app_name == "system":
            logs.extend(await collect_system_logs())
        else:
            # Generic log collection
            logs.extend(await collect_generic_logs(app_path))
            
    except Exception as e:
        logger.error(f"Error collecting logs from {app_name}: {e}")
    
    return logs

async def collect_frontend_logs() -> List[LogEntry]:
    """Collect logs from the frontend application"""
    logs = []
    
    # Check for Next.js logs
    next_logs_path = "apps/web/.next/logs"
    if os.path.exists(next_logs_path):
        for log_file in glob.glob(f"{next_logs_path}/*.log"):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            log_entry = parse_log_line(line, "frontend", log_file)
                            if log_entry:
                                logs.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to read frontend log file {log_file}: {e}")
    
    return logs

async def collect_backend_logs() -> List[LogEntry]:
    """Collect logs from the backend application"""
    logs = []
    
    # Check for Python logs
    python_logs_path = "apps/api/logs"
    if os.path.exists(python_logs_path):
        for log_file in glob.glob(f"{python_logs_path}/*.log"):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            log_entry = parse_log_line(line, "backend", log_file)
                            if log_entry:
                                logs.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to read backend log file {log_file}: {e}")
    
    return logs

async def collect_nginx_logs() -> List[LogEntry]:
    """Collect logs from Nginx"""
    logs = []
    
    nginx_log_paths = [
        "/var/log/nginx/access.log",
        "/var/log/nginx/error.log",
        "/var/log/nginx/gpucloud.access.log",
        "/var/log/nginx/gpucloud.error.log"
    ]
    
    for log_path in nginx_log_paths:
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            log_entry = parse_log_line(line, "nginx", log_path)
                            if log_entry:
                                logs.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to read nginx log file {log_path}: {e}")
    
    return logs

async def collect_system_logs() -> List[LogEntry]:
    """Collect system logs"""
    logs = []
    
    system_log_paths = [
        "/var/log/syslog",
        "/var/log/messages",
        "/var/log/kern.log"
    ]
    
    for log_path in system_log_paths:
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            log_entry = parse_log_line(line, "system", log_path)
                            if log_entry:
                                logs.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to read system log file {log_path}: {e}")
    
    return logs

async def collect_generic_logs(app_path: str) -> List[LogEntry]:
    """Collect logs from a generic path"""
    logs = []
    
    if os.path.exists(app_path):
        for log_file in glob.glob(f"{app_path}/**/*.log", recursive=True):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            log_entry = parse_log_line(line, os.path.basename(app_path), log_file)
                            if log_entry:
                                logs.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to read generic log file {log_file}: {e}")
    
    return logs

def parse_log_line(line: str, app: str, source: str) -> LogEntry:
    """Parse a log line into a LogEntry object"""
    try:
        line = line.strip()
        if not line:
            return None
        
        # Try to parse as JSON first
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return LogEntry(
                    timestamp=data.get('timestamp', datetime.now().isoformat()),
                    level=data.get('level', 'INFO'),
                    message=data.get('message', line),
                    data=data.get('data'),
                    app=app,
                    source=source
                )
        except json.JSONDecodeError:
            pass
        
        # Try to parse common log formats
        # Format: [timestamp] LEVEL: message
        if line.startswith('[') and ']' in line:
            parts = line.split(']', 1)
            if len(parts) == 2:
                timestamp = parts[0][1:]  # Remove opening bracket
                remaining = parts[1].strip()
                
                if ':' in remaining:
                    level_part, message = remaining.split(':', 1)
                    level = level_part.strip()
                    message = message.strip()
                    
                    return LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=message,
                        app=app,
                        source=source
                    )
        
        # Default parsing - treat as INFO level
        return LogEntry(
            timestamp=datetime.now().isoformat(),
            level='INFO',
            message=line,
            app=app,
            source=source
        )
        
    except Exception as e:
        logger.warning(f"Failed to parse log line: {e}")
        return None
