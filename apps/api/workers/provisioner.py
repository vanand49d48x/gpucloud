import boto3
import time
import logging
import traceback
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from sqlmodel import Session, select
from apps.api.app.db import engine
from apps.api.app.models import Pod, PodStatus, Provider
from apps.api.app.config import settings
from apps.api.app.queue import q

log = logging.getLogger(__name__)

# Production settings
MAX_RETRIES = 3
JOB_TIMEOUT_MINUTES = 10
STATUS_UPDATE_INTERVAL = 30  # seconds

def _atomic_debit(user_id: int, cents: int) -> bool:
    # Returns True if debit succeeded, False if insufficient funds.
    with Session(engine) as s:
        # Use raw SQL for atomicity
        res = s.exec(f"""
            UPDATE credits 
            SET balance_cents = balance_cents - {cents}, updated_at = NOW()
            WHERE user_id = {user_id} AND balance_cents >= {cents}
            RETURNING id
        """)
        return res.fetchone() is not None

def _update(pod_id: int, **kwargs) -> Pod | None:
    """Update pod with error handling and logging"""
    try:
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod:
                log.error(f"[update] Pod {pod_id} not found")
                return None
            
            # Update fields
            for key, value in kwargs.items():
                setattr(pod, key, value)
            
            # Always update timestamp
            pod.updated_at = datetime.utcnow()
            
            s.add(pod)
            s.commit()
            s.refresh(pod)
            
            log.info(f"[update] Pod {pod_id} updated: {kwargs}")
            return pod
            
    except Exception as e:
        log.error(f"[update] Failed to update pod {pod_id}: {e}")
        return None

def _check_job_timeout(pod_id: int, start_time: datetime) -> bool:
    """Check if job has exceeded timeout"""
    elapsed = datetime.utcnow() - start_time
    if elapsed > timedelta(minutes=JOB_TIMEOUT_MINUTES):
        log.error(f"[provision] Job timeout for pod {pod_id} after {elapsed}")
        return True
    return False

def provision_pod(pod_id: int, instance_type: str = "t3.micro"):
    """Provision a pod with comprehensive error handling and timeout protection"""
    start_time = datetime.utcnow()
    log.info(f"[provision] start pod_id={pod_id}")
    
    try:
        # Initial status update
        pod = _update(pod_id, status=PodStatus.starting)
        if not pod:
            return
        
        # Check for existing instance (prevent duplicates)
        if pod.instance_id:
            log.warning(f"[provision] Pod {pod_id} already has instance {pod.instance_id}, skipping")
            return
        
        ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
        
        # Launch instance with retry logic
        instance_id = None
        for attempt in range(MAX_RETRIES):
            try:
                if _check_job_timeout(pod_id, start_time):
                    _update(pod_id, status=PodStatus.error)
                    return
                
                log.info(f"[provision] Launch attempt {attempt + 1} for pod {pod_id}")
                
                run = ec2.run_instances(
                    ImageId=settings.BASE_AMI_ID,
                    InstanceType=instance_type,
                    MinCount=1, MaxCount=1,
                    IamInstanceProfile={"Name": settings.AWS_INSTANCE_PROFILE},
                    SubnetId=settings.AWS_SUBNET_ID,
                    SecurityGroupIds=[settings.AWS_SECURITY_GROUP_ID],
                    KeyName=settings.AWS_SSH_KEY_NAME,
                    TagSpecifications=[{
                        "ResourceType": "instance",
                        "Tags": [{"Key":"Name","Value": f"gpucloud-pod-{pod_id}"}]
                    }]
                )
                instance_id = run["Instances"][0]["InstanceId"]
                break
                
            except ClientError as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                log.warning(f"[provision] Launch attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        if not instance_id:
            raise Exception("Failed to launch instance after all retries")
        
        # Update with instance details
        _update(pod_id, instance_id=instance_id, instance_type=instance_type)
        
        # Wait for instance to be running with timeout
        log.info(f"[provision] Waiting for instance {instance_id} to be running...")
        waiter = ec2.get_waiter("instance_running")
        
        # Use waiter with timeout
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={'Delay': 10, 'MaxAttempts': 30}  # 5 minute timeout
        )
        
        if _check_job_timeout(pod_id, start_time):
            # Terminate the instance we just created
            try:
                ec2.terminate_instances(InstanceIds=[instance_id])
            except:
                pass
            _update(pod_id, status=PodStatus.error)
            return
        
        # Get instance details
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        inst = desc["Reservations"][0]["Instances"][0]
        public_ip = inst.get("PublicIpAddress")
        
        if not public_ip:
            log.warning("[provision] instance has no PublicIpAddress")
        
        # Final status update
        _update(pod_id, public_ip=public_ip, status=PodStatus.running, provider=Provider.aws)
        log.info(f"[provision] running pod_id={pod_id} ip={public_ip} id={instance_id}")
        
        # Start metering in background (non-blocking)
        _start_metering(pod_id)
        
    except ClientError as e:
        log.error(f"[provision] AWS error: {e}")
        _update(pod_id, status=PodStatus.error)
    except Exception as e:
        log.error(f"[provision] Unexpected error: {e}")
        log.error(traceback.format_exc())
        _update(pod_id, status=PodStatus.error)
        
        # Cleanup any partially created resources
        if 'instance_id' in locals() and instance_id:
            try:
                ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
                ec2.terminate_instances(InstanceIds=[instance_id])
            except:
                pass

def _start_metering(pod_id: int):
    """Start metering in background thread to avoid blocking"""
    import threading
    
    def meter_thread():
        try:
            _meter_until_stopped(pod_id)
        except Exception as e:
            log.error(f"[meter] Metering failed for pod {pod_id}: {e}")
            _update(pod_id, status=PodStatus.error)
    
    thread = threading.Thread(target=meter_thread, daemon=True)
    thread.start()

def _meter_until_stopped(pod_id: int):
    """MVP metering: every 60s, charge per-minute based on hourly_rate_cents."""
    log.info(f"[meter] start pod_id={pod_id}")
    
    while True:
        time.sleep(60)
        
        # Check if pod is still running
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod or str(pod.status) != str(PodStatus.running):
                log.info(f"[meter] pod not running, stop. pod_id={pod_id}")
                return
            
            user_id = pod.user_id
            per_minute = max(1, int(round(pod.hourly_rate_cents / 60)))
        
        # Atomic debit
        ok = _atomic_debit(user_id, per_minute)
        if not ok:
            log.info(f"[meter] credits depleted, stopping pod_id={pod_id}")
            teardown_pod(pod_id)
            return

def teardown_pod(pod_id: int):
    """Teardown a pod with comprehensive error handling and cleanup"""
    log.info(f"[teardown] start pod_id={pod_id}")
    
    try:
        # Get pod details
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod:
                log.warning(f"[teardown] Pod {pod_id} not found")
                return
            
            instance_id = pod.instance_id
            instance_type = pod.instance_type
        
        # Terminate AWS instance if it exists
        if instance_id:
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
            try:
                log.info(f"[teardown] Terminating instance {instance_id}")
                ec2.terminate_instances(InstanceIds=[instance_id])
                
                # Wait for termination to complete
                waiter = ec2.get_waiter("instance_terminated")
                waiter.wait(
                    InstanceIds=[instance_id],
                    WaiterConfig={'Delay': 5, 'MaxAttempts': 60}  # 5 minute timeout
                )
                
                log.info(f"[teardown] Instance {instance_id} terminated successfully")
                
            except ClientError as ce:
                log.warning(f"[teardown] terminate_instances: {ce}")
            except Exception as e:
                log.error(f"[teardown] Failed to terminate instance: {e}")
        
        # Update status to stopped
        _update(pod_id, status=PodStatus.stopped, instance_id=None)
        log.info(f"[teardown] done pod_id={pod_id}")
        
    except Exception as e:
        log.error(f"[teardown] Failed: {e}")
        log.error(traceback.format_exc())
        _update(pod_id, status=PodStatus.error)
