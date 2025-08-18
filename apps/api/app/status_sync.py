import asyncio
import logging
from prometheus_client import Counter, Gauge
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from sqlalchemy.orm import Session
from sqlalchemy import and_

from apps.api.app.db import engine
from apps.api.app.models import Pod
from apps.api.app.config import settings

logger = logging.getLogger(__name__)

class StatusSyncManager:
    # Prometheus metrics
    sync_success_counter = Counter('pod_status_sync_success_total', 'Total successful pod status syncs')
    sync_failure_counter = Counter('pod_status_sync_failure_total', 'Total failed pod status syncs')
    sync_pod_gauge = Gauge('pod_status_sync_pods', 'Number of pods synced per batch')
    sync_last_timestamp = Gauge('pod_status_sync_last_timestamp', 'Last successful sync timestamp')
    sync_aws_throttle_counter = Counter('pod_status_sync_aws_throttle_total', 'Total AWS API throttling events')
    def __init__(self):
        self.ec2_client = boto3.client(
            'ec2',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.sync_interval = int(getattr(settings, "SYNC_INTERVAL", 30))  # seconds, configurable
        self.running = False
        self.max_batch_size = 1000  # AWS EC2 describe_instances limit
        self.max_retries = 3
        self.base_backoff = 2
        
    async def start_sync_loop(self):
        """Start the periodic status sync loop"""
        self.running = True
        logger.info("Starting periodic status sync loop")
        
        while self.running:
            try:
                await self.sync_all_pod_statuses()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"Error in status sync loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    def stop_sync_loop(self):
        """Stop the periodic status sync loop"""
        self.running = False
        logger.info("Stopping periodic status sync loop")
    
    async def sync_all_pod_statuses(self):
        """Sync status of all pods with AWS"""
        try:
            # Get all pods from database
            from apps.api.app.db import engine
            with Session(engine) as db:
                pods = db.query(Pod).filter(
                    Pod.instance_id.isnot(None),
                    Pod.status.in_(['starting', 'stopping', 'running', 'stopped', 'error'])
                ).all()
                
                if not pods:
                    return
                
                # Get instance IDs
                instance_ids = [pod.instance_id for pod in pods if pod.instance_id]
                if not instance_ids:
                    return
                # Batch instance IDs
                aws_statuses = {}
                batch_count = 0
                for i in range(0, len(instance_ids), self.max_batch_size):
                    batch = instance_ids[i:i+self.max_batch_size]
                    batch_count += 1
                    logger.info(f"Syncing batch {batch_count}: {len(batch)} instances")
                    batch_statuses = self._get_aws_instance_statuses_with_retry(batch)
                    aws_statuses.update(batch_statuses)
                self.sync_pod_gauge.set(len(instance_ids))
                
                # Update database based on AWS status
                updated_count = 0
                for pod in pods:
                    if pod.instance_id in aws_statuses:
                        aws_status = aws_statuses[pod.instance_id]
                        new_status = self._map_aws_to_pod_status(aws_status)
                        
                        if new_status and new_status != pod.status:
                            old_status = pod.status
                            pod.status = new_status
                            pod.updated_at = datetime.utcnow()
                            
                            logger.info({
                                "event": "pod_status_update",
                                "pod_id": pod.id,
                                "old_status": old_status,
                                "new_status": new_status,
                                "aws_status": aws_status,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            updated_count += 1
                    
                    # Handle terminated instances
                    elif pod.instance_id and pod.status not in ['stopped', 'error']:
                        # Instance not found in AWS - might be terminated
                        logger.warning({
                            "event": "pod_instance_missing",
                            "pod_id": pod.id,
                            "instance_id": pod.instance_id,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        pod.status = 'stopped'
                        pod.updated_at = datetime.utcnow()
                        updated_count += 1
                
                if updated_count > 0:
                    db.commit()
                    logger.info({
                        "event": "pod_status_batch_update",
                        "updated_count": updated_count,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    self.sync_success_counter.inc()
                    self.sync_last_timestamp.set_to_current_time()
                else:
                    logger.info({
                        "event": "pod_status_no_update",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            logger.error({
                "event": "pod_status_sync_error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            self.sync_failure_counter.inc()
    
    def _get_aws_instance_statuses_with_retry(self, instance_ids: List[str]) -> Dict[str, str]:
        """Get current status of EC2 instances from AWS with retry and backoff"""
        attempt = 0
        while attempt < self.max_retries:
            try:
                response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
                statuses = {}
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        state = instance['State']['Name']
                        statuses[instance_id] = state
                return statuses
            except Exception as e:
                attempt += 1
                is_throttle = 'Throttling' in str(e)
                logger.error({
                    "event": "aws_describe_instances_error",
                    "error": str(e),
                    "attempt": attempt,
                    "instance_ids": instance_ids,
                    "timestamp": datetime.utcnow().isoformat()
                })
                if is_throttle:
                    self.sync_aws_throttle_counter.inc()
                if attempt < self.max_retries:
                    backoff = self.base_backoff ** attempt
                    logger.info({
                        "event": "aws_describe_instances_retry",
                        "attempt": attempt,
                        "backoff": backoff,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    asyncio.sleep(backoff)
                else:
                    logger.error({
                        "event": "aws_describe_instances_giveup",
                        "error": str(e),
                        "instance_ids": instance_ids,
                        "timestamp": datetime.utcnow().isoformat()
                    })
        return {}
    
    def _map_aws_to_pod_status(self, aws_status: str) -> str:
        """Map AWS EC2 status to pod status according to the guidance"""
        status_mapping = {
            'pending': 'starting',
            'running': 'running',
            'stopping': 'stopping',
            'stopped': 'stopped',
            'shutting-down': 'stopping',
            'terminated': 'stopped',
            'error': 'error'
        }
        return status_mapping.get(aws_status, aws_status)
    
    async def sync_single_pod_status(self, pod_id: int) -> bool:
        """Sync status of a single pod with AWS"""
        try:
            db = next(get_session())
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod or not pod.instance_id:
                return False
            
            aws_statuses = self._get_aws_instance_statuses([pod.instance_id])
            
            if pod.instance_id in aws_statuses:
                aws_status = aws_statuses[pod.instance_id]
                new_status = self._map_aws_to_pod_status(aws_status)
                
                if new_status and new_status != pod.status:
                    old_status = pod.status
                    pod.status = new_status
                    pod.updated_at = datetime.utcnow()
                    db.commit()
                    
                    logger.info(f"Pod {pod.id} status synced: {old_status} → {new_status} (AWS: {aws_status})")
                    return True
            else:
                # Instance not found - might be terminated
                if pod.status not in ['stopped', 'error']:
                    pod.status = 'stopped'
                    pod.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Pod {pod.id} marked as stopped (instance not found in AWS)")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error syncing pod {pod_id} status: {e}")
            if 'db' in locals():
                db.rollback()
            return False

# Global instance
status_sync_manager = StatusSyncManager()

async def start_status_sync():
    """Start the status sync manager"""
    await status_sync_manager.start_sync_loop()

def stop_status_sync():
    """Stop the status sync manager"""
    status_sync_manager.stop_sync_loop()
