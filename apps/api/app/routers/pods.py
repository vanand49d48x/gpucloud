from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from apps.api.app.db import get_session
from apps.api.app.models import Pod, Credits, PodStatus, Provider
from apps.api.app.deps import current_user
from apps.api.app.templates import TEMPLATES
from apps.api.app.queue import q
from apps.api.app.health_checker import health_checker
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["pods"])

class CreatePodIn(BaseModel):
    template_id: str

@router.get("/templates")
def list_templates():
    return [{"id": k, **v} for k, v in TEMPLATES.items()]

@router.get("/health")
def get_system_health():
    """Get overall system health status"""
    return health_checker.get_health_status()

@router.post("/pods")
def create_pod(body: CreatePodIn, session: Session = Depends(get_session), user=Depends(current_user)):
    tpl = TEMPLATES.get(body.template_id)
    if not tpl:
        raise HTTPException(status_code=400, detail="unknown template")
    # credit check: at least 1 min worth
    min_needed = tpl["hourly_rate_cents"] // 60 or 1
    credits = session.query(Credits).filter(Credits.user_id == user.id).first()
    if not credits or credits.balance_cents < min_needed:
        raise HTTPException(status_code=402, detail="insufficient credits")

    pod = Pod(
        user_id=user.id,
        status=PodStatus.pending,
        provider=Provider.aws,
        hourly_rate_cents=tpl["hourly_rate_cents"],
        instance_type=tpl["instance_type"],  # Set instance_type during creation
    )
    session.add(pod); session.commit(); session.refresh(pod)

    # enqueue real provisioner (string import path)
    job = q.enqueue("apps.api.workers.provisioner.provision_pod", pod.id, tpl["instance_type"])
    logger.info(f"Enqueued provision job {job.id} for pod {pod.id}")
    return {"id": pod.id, "status": pod.status}

@router.get("/pods")
def list_pods(session: Session = Depends(get_session), user=Depends(current_user)):
    rows = session.query(Pod).filter(Pod.user_id == user.id).order_by(Pod.id.desc()).all()
    return [
        {
            "id": p.id,
            "status": p.status,
            "public_ip": p.public_ip,
            "template": None,  # we'll store template later if needed
            "hourly_rate_cents": p.hourly_rate_cents,
            "instance_id": p.instance_id,
            "instance_type": p.instance_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "gpu_type": p.gpu_type,
            "vram_gb": p.vram_gb,
        }
        for p in rows
    ]

@router.post("/pods/{pod_id}/stop")
def stop_pod(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    try:
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="pod not found")
        
        if pod.status in (PodStatus.stopping, PodStatus.stopped):
            return {"id": pod.id, "status": pod.status}
        
        # Preserve instance_type before stopping (for restart capability)
        instance_type = pod.instance_type
        
        # enqueue stop (pause instance, do not terminate)
        job = q.enqueue("apps.api.workers.provisioner.stop_pod", pod.id)
        logger.info(f"Enqueued stop job {job.id} for pod {pod.id} (stop, not terminate)")
        
        pod.status = PodStatus.stopping
        session.add(pod); session.commit()
        return {"id": pod.id, "status": str(pod.status)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop pod")

@router.post("/pods/{pod_id}/start")
def start_pod(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    try:
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="pod not found")
        
        if pod.status in (PodStatus.starting, PodStatus.running):
            return {"id": pod.id, "status": pod.status}
        
        if pod.status == PodStatus.stopped:
            # Credit check: require at least 1 minute worth
            min_needed = max(1, round(pod.hourly_rate_cents / 60))
            credits = session.query(Credits).filter(Credits.user_id == user.id).first()
            if not credits or credits.balance_cents < min_needed:
                raise HTTPException(
                    status_code=402, 
                    detail=f"Insufficient credits. Need at least {min_needed} cents, have {credits.balance_cents if credits else 0}"
                )

            # If we have a preserved instance_id, start the existing instance (preferred)
            if pod.instance_id:
                job = q.enqueue("apps.api.workers.provisioner.start_stopped_pod", pod.id)
                logger.info(f"Enqueued start-existing job {job.id} for pod {pod.id} (instance {pod.instance_id})")
            else:
                # Fallback: no instance preserved, provision new using stored instance_type
                if not pod.instance_type:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot restart pod: instance type not available. Please deploy a new pod."
                    )
                job = q.enqueue("apps.api.workers.provisioner.provision_pod", pod.id, pod.instance_type)
                logger.info(f"Enqueued restart-new job {job.id} for pod {pod.id}")

            pod.status = PodStatus.starting
            session.add(pod); session.commit()
            return {"id": pod.id, "status": str(pod.status)}
        
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot start pod in {pod.status} status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start pod")

@router.post("/pods/{pod_id}/force-reset")
def force_reset_pod(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    """Force reset a stuck pod to stopped status (admin/emergency use)"""
    try:
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="pod not found")
        
        if pod.status not in (PodStatus.starting, PodStatus.stopping):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot reset pod in {pod.status} status"
            )
        
        # Force reset to stopped but preserve instance_id for restart capability
        pod.status = PodStatus.stopped
        # Preserve instance_id and instance_type for restart capability
        # Only clear public_ip as it changes on restart
        pod.public_ip = None
        session.add(pod)
        session.commit()
        
        logger.warning(f"Force reset pod {pod_id} from {pod.status} to stopped by user {user.id} (preserving instance_id)")
        return {"id": pod.id, "status": "stopped", "message": "Pod force reset to stopped status (instance_id preserved for restart)"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force reset pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset pod")

@router.post("/pods/{pod_id}/sync-status")
async def sync_pod_status(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    """Manually trigger status sync for a specific pod"""
    try:
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="Pod not found")
        
        # Import here to avoid circular imports
        from ..status_sync import StatusSyncManager
        
        # Create status sync manager and sync this specific pod
        manager = StatusSyncManager()
        success = await manager.sync_single_pod_status(pod_id)
        
        if success:
            # Refresh the pod data to get updated status
            session.refresh(pod)
            return {
                "id": pod.id, 
                "status": pod.status,
                "message": "Status sync completed successfully"
            }
        else:
            return {
                "id": pod.id,
                "status": pod.status, 
                "message": "Status sync completed but no changes made"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync status for pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync pod status")

@router.delete("/pods/{pod_id}")
def delete_pod(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    """Delete a pod completely - stop if running, terminate AWS instance, and remove from database"""
    try:
        pod = session.get(Pod, pod_id)
        if not pod or pod.user_id != user.id:
            raise HTTPException(status_code=404, detail="pod not found")
        
        # If pod is running, terminate it first
        if pod.status in (PodStatus.running, PodStatus.starting):
            logger.info(f"Terminating running pod {pod_id} before deletion")
            # Enqueue teardown job to terminate the instance
            job = q.enqueue("apps.api.workers.provisioner.teardown_pod", pod.id)
            logger.info(f"Enqueued teardown job {job.id} for pod {pod.id} before deletion")
            
            # Update status to stopping
            pod.status = PodStatus.stopping
            session.add(pod)
            session.commit()
            
            # Return early - user should wait for pod to terminate before deleting
            return {
                "id": pod.id, 
                "status": str(pod.status),
                "message": "Pod is being terminated. Please wait for it to terminate completely before deleting."
            }
        
        # If pod is stopping, return error
        if pod.status == PodStatus.stopping:
            raise HTTPException(
                status_code=400, 
                detail="Pod is currently terminating. Please wait for it to terminate completely before deleting."
            )
        
        # For stopped/error pods, proceed with deletion
        instance_id = pod.instance_id
        
        # Terminate AWS instance if it exists and is not already terminated
        if instance_id:
            try:
                import boto3
                from apps.api.app.config import settings
                
                ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
                
                # Check instance status
                response = ec2.describe_instances(InstanceIds=[instance_id])
                if response['Reservations']:
                    instance = response['Reservations'][0]['Instances'][0]
                    if instance['State']['Name'] not in ['terminated', 'shutting-down']:
                        logger.info(f"Terminating instance {instance_id} for pod deletion")
                        ec2.terminate_instances(InstanceIds=[instance_id])
                        
                        # Wait for termination to complete
                        waiter = ec2.get_waiter("instance_terminated")
                        waiter.wait(
                            InstanceIds=[instance_id],
                            WaiterConfig={'Delay': 5, 'MaxAttempts': 60}  # 5 minute timeout
                        )
                        logger.info(f"Instance {instance_id} terminated successfully")
                    else:
                        logger.info(f"Instance {instance_id} already terminated")
                        
            except Exception as e:
                logger.warning(f"Failed to terminate instance {instance_id}: {e}")
                # Continue with deletion even if AWS cleanup fails
        
        # Remove from database
        session.delete(pod)
        session.commit()
        
        logger.info(f"Pod {pod_id} deleted successfully")
        return {
            "id": pod_id,
            "message": "Pod deleted successfully",
            "instance_terminated": bool(instance_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete pod {pod_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete pod")
