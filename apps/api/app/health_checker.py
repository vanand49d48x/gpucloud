#!/usr/bin/env python3
"""
GPUCloud Health Checker - Production Monitoring & Auto-Recovery
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional
from sqlmodel import Session, select
from apps.api.app.db import engine
from apps.api.app.models import Pod, PodStatus
from apps.api.app.queue import q
# Import these functions only when needed to avoid circular imports
# from apps.api.workers.provisioner import teardown_pod, provision_pod

logger = logging.getLogger(__name__)

class HealthChecker:
    """Production health monitoring and auto-recovery system"""
    
    def __init__(self):
        self.check_interval = 60  # Check every minute
        self.stuck_threshold = 10  # Consider stuck after 10 minutes
        self.max_recovery_attempts = 3
        
    def start_monitoring(self):
        """Start the health monitoring loop"""
        logger.info("Starting GPUCloud health monitoring...")
        
        while True:
            try:
                self.check_all_pods()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                time.sleep(self.check_interval)
    
    def check_all_pods(self):
        """Check all pods for health issues"""
        try:
            with Session(engine) as session:
                # Find pods that might be stuck
                stuck_pods = self._find_stuck_pods(session)
                
                if stuck_pods:
                    logger.warning(f"Found {len(stuck_pods)} stuck pods, attempting recovery...")
                    self._recover_stuck_pods(stuck_pods)
                
                # Check for orphaned instances
                self._check_orphaned_instances(session)
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def _find_stuck_pods(self, session: Session) -> List[Pod]:
        """Find pods stuck in intermediate states"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.stuck_threshold)
        
        stuck_pods = session.query(Pod).filter(
            Pod.status.in_([PodStatus.starting, PodStatus.stopping]),
            Pod.updated_at < cutoff_time
        ).all()
        
        return stuck_pods
    
    def _recover_stuck_pods(self, stuck_pods: List[Pod]):
        """Attempt to recover stuck pods"""
        for pod in stuck_pods:
            try:
                logger.info(f"Attempting to recover stuck pod {pod.id} (status: {pod.status})")
                
                if pod.status == PodStatus.starting:
                    self._recover_stuck_starting_pod(pod)
                elif pod.status == PodStatus.stopping:
                    self._recover_stuck_stopping_pod(pod)
                    
            except Exception as e:
                logger.error(f"Failed to recover pod {pod.id}: {e}")
    
    def _recover_stuck_starting_pod(self, pod: Pod):
        """Recover a pod stuck in 'starting' status"""
        try:
            # Check if we have an instance ID
            if pod.instance_id:
                # Pod has instance but is stuck, check AWS status
                import boto3
                from apps.api.app.settings import settings
                
                ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
                response = ec2.describe_instances(InstanceIds=[pod.instance_id])
                
                if response['Reservations']:
                    instance = response['Reservations'][0]['Instances'][0]
                    state = instance['State']['Name']
                    
                    if state == 'running':
                        # Instance is running, update pod status
                        with Session(engine) as session:
                            pod.public_ip = instance.get('PublicIpAddress')
                            pod.status = PodStatus.running
                            pod.updated_at = datetime.utcnow()
                            session.add(pod)
                            session.commit()
                            logger.info(f"Recovered pod {pod.id} to running status")
                    elif state in ['terminated', 'stopped']:
                        # Instance is gone, reset pod
                        self._reset_pod_to_stopped(pod.id)
                    else:
                        # Instance still starting, let it continue
                        logger.info(f"Pod {pod.id} instance {pod.instance_id} still in {state} state")
                else:
                    # Instance not found, reset pod
                    self._reset_pod_to_stopped(pod.id)
            else:
                # No instance ID, reset pod
                self._reset_pod_to_stopped(pod.id)
                
        except Exception as e:
            logger.error(f"Failed to recover starting pod {pod.id}: {e}")
            # Fallback: reset to stopped
            self._reset_pod_to_stopped(pod.id)
    
    def _recover_stuck_stopping_pod(self, pod: Pod):
        """Recover a pod stuck in 'stopping' status"""
        try:
            # Force teardown
            logger.info(f"Force teardown for stuck stopping pod {pod.id}")
            
            # Enqueue teardown job
            q.enqueue("apps.api.workers.provisioner.teardown_pod", pod.id)
            
            # Update status to indicate recovery attempt
            with Session(engine) as session:
                pod.status = PodStatus.stopping
                pod.updated_at = datetime.utcnow()
                session.add(pod)
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to recover stopping pod {pod.id}: {e}")
            # Fallback: reset to stopped
            self._reset_pod_to_stopped(pod.id)
    
    def _reset_pod_to_stopped(self, pod_id: int):
        """Reset a pod to stopped status but preserve instance_id for restart capability"""
        try:
            with Session(engine) as session:
                pod = session.get(Pod, pod_id)
                if pod:
                    pod.status = PodStatus.stopped
                    # Preserve instance_id and instance_type for restart capability
                    # Only clear public_ip as it changes on restart
                    pod.public_ip = None
                    pod.updated_at = datetime.utcnow()
                    session.add(pod)
                    session.commit()
                    logger.info(f"Reset pod {pod_id} to stopped status (preserving instance_id)")
                    
        except Exception as e:
            logger.error(f"Failed to reset pod {pod_id}: {e}")
    
    def _check_orphaned_instances(self, session: Session):
        """Check for AWS instances that don't have corresponding pods"""
        try:
            # This would require AWS API calls to check for orphaned instances
            # Implementation depends on your specific needs
            pass
        except Exception as e:
            logger.error(f"Orphaned instance check failed: {e}")
    
    def get_health_status(self) -> dict:
        """Get current system health status"""
        try:
            with Session(engine) as session:
                total_pods = session.query(Pod).all()
                
                status_counts = {}
                for status in PodStatus:
                    count = len([p for p in total_pods if p.status == status])
                    status_counts[status] = count
                
                # Check for stuck pods
                cutoff_time = datetime.utcnow() - timedelta(minutes=self.stuck_threshold)
                stuck_pods = session.query(Pod).filter(
                    Pod.status.in_([PodStatus.starting, PodStatus.stopping]),
                    Pod.updated_at < cutoff_time
                ).all()
                
                return {
                    "status": "healthy" if not stuck_pods else "degraded",
                    "total_pods": len(total_pods),
                    "status_counts": status_counts,
                    "stuck_pods": len(stuck_pods),
                    "last_check": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }

# Global health checker instance
health_checker = HealthChecker()

def start_health_monitoring():
    """Start health monitoring in background thread"""
    import threading
    
    def monitor_thread():
        health_checker.start_monitoring()
    
    thread = threading.Thread(target=monitor_thread, daemon=True)
    thread.start()
    logger.info("Health monitoring started in background thread")

if __name__ == "__main__":
    # Run health checker standalone for testing
    logging.basicConfig(level=logging.INFO)
    health_checker.start_monitoring()
