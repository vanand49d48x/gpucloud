from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import List, Optional
from apps.api.app.db import get_session
from apps.api.app.models import Pod
from apps.api.app.deps import current_user
from apps.api.app.config import settings
import boto3
import logging
from datetime import datetime

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

class CloudWatchLogEntry(BaseModel):
    timestamp: str
    message: str
    log_stream: str

class PodLogsResponse(BaseModel):
    pod_id: int
    log_group: str
    log_entries: List[CloudWatchLogEntry]
    total_entries: int
    next_token: Optional[str] = None

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

@router.get("/pods/{pod_id}/cloudwatch")
def get_pod_cloudwatch_logs(
    pod_id: int,
    session: Session = Depends(get_session),
    user=Depends(current_user),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[str] = Query(None, description="ISO timestamp for start time"),
    end_time: Optional[str] = Query(None, description="ISO timestamp for end time"),
    next_token: Optional[str] = Query(None, description="Pagination token")
):
    """Get CloudWatch logs for a specific pod"""
    try:
        # Verify pod belongs to user
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="Pod not found")
        
        # Check if pod has CloudWatch logging enabled
        if not pod.log_group:
            raise HTTPException(
                status_code=400, 
                detail="Pod does not have CloudWatch logging enabled"
            )

        # Check if pod has IAM role configured
        if not pod.role_arn:
            raise HTTPException(
                status_code=400,
                detail="Pod does not have IAM role configured"
            )

        # Assume the pod's IAM role to access CloudWatch logs
        # This ensures the backend uses the pod's permissions, not its own
        sts_client = boto3.client(
            'sts',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        try:
            # Assume the pod's role temporarily
            assumed_role = sts_client.assume_role(
                RoleArn=pod.role_arn,
                RoleSessionName=f"gpucloud-logs-{pod_id}"
            )

            # Create CloudWatch client with assumed role credentials
            logs_client = boto3.client(
                'logs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                aws_session_token=assumed_role['Credentials']['SessionToken']
            )

        except Exception as e:
            logger.error(f"Failed to assume role {pod.role_arn}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to assume pod IAM role"
            )
        
        # Prepare filter parameters
        filter_params = {
            'logGroupName': pod.log_group,
            'limit': limit
        }
        
        if start_time:
            filter_params['startTime'] = int(datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp() * 1000)
        
        if end_time:
            filter_params['endTime'] = int(datetime.fromisoformat(end_time.replace('Z', '+00:00')).timestamp() * 1000)
        
        if next_token:
            filter_params['nextToken'] = next_token
        
        # Get log events
        response = logs_client.filter_log_events(**filter_params)
        
        # Parse log entries
        log_entries = []
        for event in response.get('events', []):
            log_entries.append(CloudWatchLogEntry(
                timestamp=datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                message=event['message'],
                log_stream=event['logStreamName']
            ))
        
        return PodLogsResponse(
            pod_id=pod_id,
            log_group=pod.log_group,
            log_entries=log_entries,
            total_entries=len(log_entries),
            next_token=response.get('nextToken')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CloudWatch logs for pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve CloudWatch logs")

@router.get("/pods/{pod_id}/cloudwatch/streams")
def get_pod_log_streams(
    pod_id: int,
    session: Session = Depends(get_session),
    user=Depends(current_user)
):
    """Get available log streams for a pod"""
    try:
        # Verify pod belongs to user
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="Pod not found")
        
        # Check if pod has CloudWatch logging enabled
        if not pod.log_group:
            raise HTTPException(
                status_code=400, 
                detail="Pod does not have CloudWatch logging enabled"
            )

        # Check if pod has IAM role configured
        if not pod.role_arn:
            raise HTTPException(
                status_code=400,
                detail="Pod does not have IAM role configured"
            )

        # Assume the pod's IAM role to access CloudWatch logs
        # This ensures the backend uses the pod's permissions, not its own
        sts_client = boto3.client(
            'sts',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        try:
            # Assume the pod's role temporarily
            assumed_role = sts_client.assume_role(
                RoleArn=pod.role_arn,
                RoleSessionName=f"gpucloud-logs-{pod_id}"
            )

            # Create CloudWatch client with assumed role credentials
            logs_client = boto3.client(
                'logs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                aws_session_token=assumed_role['Credentials']['SessionToken']
            )

        except Exception as e:
            logger.error(f"Failed to assume role {pod.role_arn}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to assume pod IAM role"
            )
        
        # Get log streams
        response = logs_client.describe_log_streams(
            logGroupName=pod.log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=50
        )
        
        streams = []
        for stream in response.get('logStreams', []):
            streams.append({
                "name": stream['logStreamName'],
                "first_event_time": stream.get('firstEventTime'),
                "last_event_time": stream.get('lastEventTime'),
                "stored_bytes": stream.get('storedBytes', 0)
            })
        
        return {
            "pod_id": pod_id,
            "log_group": pod.log_group,
            "log_streams": streams,
            "total_streams": len(streams)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log streams for pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve log streams")

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
