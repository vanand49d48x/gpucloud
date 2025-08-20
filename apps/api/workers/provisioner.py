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
from apps.api.app.models import User

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Production settings
MAX_RETRIES = 3
JOB_TIMEOUT_MINUTES = 10
STATUS_UPDATE_INTERVAL = 30  # seconds

def _atomic_debit(user_id: int, cents: int) -> bool:
    # Returns True if debit succeeded, False if insufficient funds.
    with Session(engine) as s:
        # Use raw SQL for atomicity
        from sqlalchemy import text
        res = s.execute(text(f"""
            UPDATE credits 
            SET balance_cents = balance_cents - {cents}, updated_at = NOW()
            WHERE user_id = {user_id} AND balance_cents >= {cents}
            RETURNING id
        """))
        return res.fetchone() is not None

def _update(pod_id: int, **kwargs) -> Pod | None:
    """Update pod with error handling and logging"""
    try:
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod:
                print(f"DEBUG: [update] Pod {pod_id} not found")
                return None
            
            # Update fields
            for key, value in kwargs.items():
                setattr(pod, key, value)
            
            # Always update timestamp
            pod.updated_at = datetime.utcnow()
            
            s.add(pod)
            s.commit()
            s.refresh(pod)
            
            print(f"DEBUG: [update] Pod {pod_id} updated: {kwargs}")
            return pod
            
    except Exception as e:
        print(f"DEBUG: [update] Failed to update pod {pod_id}: {e}")
        return None

def _check_job_timeout(pod_id: int, start_time: datetime) -> bool:
    """Check if job has exceeded timeout"""
    elapsed = time.time() - start_time
    if elapsed > JOB_TIMEOUT_MINUTES * 60:
        print(f"DEBUG: [provision] Job timeout for pod {pod_id} after {elapsed}")
        return True
    return False

def start_stopped_pod(pod_id: int):
    """Start a stopped pod by starting the existing EC2 instance"""
    print(f"DEBUG: Starting stopped pod {pod_id}")
    
    with Session(engine) as db:
        try:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return
            
            if not pod.instance_id:
                logger.error(f"Pod {pod_id} has no instance_id, cannot start")
                return

            # Update status to starting
            pod.status = 'starting'
            db.commit()
            
            logger.info(f"[start_stopped] start pod_id={pod_id} instance_id={pod.instance_id}")
            
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Start the existing stopped EC2 instance
            print(f"DEBUG: Starting stopped instance {pod.instance_id}")
            ec2.start_instances(InstanceIds=[pod.instance_id])
            
            # Wait for instance to be running
            print(f"DEBUG: Waiting for instance {pod.instance_id} to be running...")
            waiter = ec2.get_waiter("instance_running")
            waiter.wait(InstanceIds=[pod.instance_id])

            # Get updated instance details
            print(f"DEBUG: Instance {pod.instance_id} is now running, getting details...")
            desc = ec2.describe_instances(InstanceIds=[pod.instance_id])
            inst = desc["Reservations"][0]["Instances"][0]
            public_ip = inst.get("PublicIpAddress")

            if not public_ip:
                print(f"DEBUG: [start_stopped] instance has no PublicIpAddress")
            else:
                print(f"DEBUG: Got public IP: {public_ip}")

            # Update pod with new public IP and set to running
            pod.public_ip = public_ip
            pod.status = 'running'
            db.commit()
            
            print(f"DEBUG: [start_stopped] running pod_id={pod_id} ip={public_ip} id={pod.instance_id}")
            logger.info(f"Pod {pod_id} started successfully (existing instance {pod.instance_id})")

            # Start metering in background
            _start_metering(pod_id)
            
        except Exception as e:
            print(f"DEBUG: Error starting stopped pod {pod_id}: {e}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            # Set status to error
            try:
                pod.status = 'error'
                db.commit()
            except:
                # If pod variable doesn't exist, fetch it again
                pod = db.query(Pod).filter(Pod.id == pod_id).first()
                if pod:
                    pod.status = 'error'
                    db.commit()
            raise

def provision_pod(pod_id: int, instance_type: str = "t3.micro"):
    """Provision a pod with enhanced error handling and per-pod IAM support"""
    print(f"DEBUG: Starting pod provision for pod {pod_id}")
    
    # Check if per-pod IAM is enabled
    if getattr(settings, 'ENABLE_PER_POD_IAM', False):
        print(f"DEBUG: Using per-pod IAM for pod {pod_id}")
        _provision_pod_with_per_pod_iam(pod_id, instance_type)
    else:
        print(f"DEBUG: Using legacy provisioning for pod {pod_id}")
        _provision_pod_legacy(pod_id, instance_type)

def _provision_pod_with_per_pod_iam(pod_id: int, instance_type: str):
    """Provision pod using per-pod IAM roles and instance profiles"""
    try:
        from apps.api.app.pod_creator import PodCreator
        
        with Session(engine) as db:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return
            
            # Get user for customer_id
            user = db.query(User).filter(User.id == pod.user_id).first()
            if not user:
                logger.error(f"User not found for pod {pod_id}")
                return
            
            # Update status to starting
            pod.status = PodStatus.starting
            db.commit()
            
            # Initialize pod creator
            creator = PodCreator()
            
            # Create pod with per-pod IAM
            result = creator.create_pod(
                customer_id=str(user.id),
                pod_id=str(pod_id),
                ami_id=settings.BASE_AMI_ID,
                instance_type=instance_type,
                subnet_id=settings.AWS_SUBNET_ID,
                sg_id=settings.AWS_SECURITY_GROUP_ID,
                key_name=settings.AWS_SSH_KEY_NAME if settings.AWS_SSH_KEY_NAME else None,
                volume_size_gb=60
            )
            
            # Update pod with results
            pod.instance_id = result["instance_id"]
            pod.instance_type = instance_type
            pod.public_ip = result.get("public_ip")
            pod.status = PodStatus.running
            
            # Store additional metadata
            pod.role_name = result.get("role_name")
            pod.role_arn = result.get("role_arn")
            pod.instance_profile = result.get("instance_profile")
            pod.log_group = result.get("log_group")
            
            db.commit()
            
            print(f"DEBUG: [per_pod_iam] running pod_id={pod_id} ip={result.get('public_ip')} id={result['instance_id']}")
            logger.info(f"Pod {pod_id} provisioned successfully with per-pod IAM: {result}")
            
            # Start metering in background
            _start_metering(pod_id)
            
    except Exception as e:
        print(f"DEBUG: Error provisioning pod {pod_id} with per-pod IAM: {e}")
        print(f"DEBUG: Exception type: {type(e).__name__}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        
        # Set status to error
        try:
            with Session(engine) as db:
                pod = db.query(Pod).filter(Pod.id == pod_id).first()
                if pod:
                    pod.status = 'error'
                    db.commit()
        except:
            pass
        raise

def _provision_pod_legacy(pod_id: int, instance_type: str):
    """Legacy pod provisioning using shared instance profile"""
    # Keep session open for the entire function
    with Session(engine) as db:
        try:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return

            # Check if this is a restart of a stopped pod with existing instance
            # Note: API may set status to 'starting' before the worker runs. If we still
            # have an instance_id, treat it as a restart of a previously stopped instance.
            if pod.instance_id and (pod.status == PodStatus.stopped or pod.status == PodStatus.starting):
                print(f"DEBUG: Pod {pod_id} has existing instance {pod.instance_id}, starting stopped instance")
                
                # Update status to starting
                pod.status = PodStatus.starting
                db.commit()
                
                logger.info(f"[start_stopped] start pod_id={pod_id} instance_id={pod.instance_id}")
                
                ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                                  aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

                # Start the existing stopped EC2 instance
                print(f"DEBUG: Starting stopped instance {pod.instance_id}")
                ec2.start_instances(InstanceIds=[pod.instance_id])
                
                # Wait for instance to be running
                print(f"DEBUG: Waiting for instance {pod.instance_id} to be running...")
                waiter = ec2.get_waiter("instance_running")
                waiter.wait(InstanceIds=[pod.instance_id])

                # Get updated instance details
                print(f"DEBUG: Instance {pod.instance_id} is now running, getting details...")
                desc = ec2.describe_instances(InstanceIds=[pod.instance_id])
                inst = desc["Reservations"][0]["Instances"][0]
                public_ip = inst.get("PublicIpAddress")

                if not public_ip:
                    print(f"DEBUG: [start_stopped] instance has no PublicIpAddress")
                else:
                    print(f"DEBUG: Got public IP: {public_ip}")

                # Update pod with new public IP and set to running
                pod.public_ip = public_ip
                pod.status = PodStatus.running
                db.commit()
                
                print(f"DEBUG: [start_stopped] running pod_id={pod_id} ip={public_ip} id={pod.instance_id}")
                logger.info(f"Pod {pod_id} started successfully (existing instance {pod.instance_id})")

                # Start metering in background
                _start_metering(pod_id)
                return

            # Update status to starting
            pod.status = PodStatus.starting
            db.commit()
            
            # AWS EC2 provisioning logic for new instances
            logger.info(f"[provision] start pod_id={pod_id}")
            
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Launch EC2 instance
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
            
            # Update pod with instance_id and instance_type
            pod.instance_id = instance_id
            pod.instance_type = instance_type
            db.commit()
            
            print(f"DEBUG: [provision] launched instance {instance_id} for pod {pod_id}")

            # Wait until running, then fetch PublicIpAddress
            print(f"DEBUG: Waiting for instance {instance_id} to be running...")
            waiter = ec2.get_waiter("instance_running")
            waiter.wait(InstanceIds=[instance_id])

            print(f"DEBUG: Instance {instance_id} is now running, getting details...")
            desc = ec2.describe_instances(InstanceIds=[instance_id])
            inst = desc["Reservations"][0]["Instances"][0]
            public_ip = inst.get("PublicIpAddress")

            if not public_ip:
                print(f"DEBUG: [provision] instance has no PublicIpAddress")
            else:
                print(f"DEBUG: Got public IP: {public_ip}")

            # Update pod with final details and set to running
            pod.public_ip = public_ip
            pod.status = PodStatus.running
            db.commit()
            
            print(f"DEBUG: [provision] running pod_id={pod_id} ip={public_ip} id={instance_id}")

            # Start metering in background
            _start_metering(pod_id)
            
        except Exception as e:
            print(f"DEBUG: Error provisioning pod {pod_id}: {e}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            # Set status to error
            try:
                pod.status = 'error'
                db.commit()
            except:
                # If pod variable doesn't exist, fetch it again
                pod = db.query(Pod).filter(Pod.id == pod_id).first()
                if pod:
                    pod.status = 'error'
                    db.commit()
            raise

def _start_metering(pod_id: int):
    """Start metering in background thread to avoid blocking"""
    import threading
    
    def meter_thread():
        try:
            _meter_until_stopped(pod_id)
        except Exception as e:
            print(f"DEBUG: [meter] Metering failed for pod {pod_id}: {e}")
            _update(pod_id, status=PodStatus.error)
    
    thread = threading.Thread(target=meter_thread, daemon=True)
    thread.start()

def _meter_until_stopped(pod_id: int):
    """MVP metering: every 60s, charge per-minute based on hourly_rate_cents."""
    print(f"DEBUG: [meter] start pod_id={pod_id}")
    
    while True:
        time.sleep(60)
        
        # Check if pod is still running
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod or str(pod.status) != str(PodStatus.running):
                print(f"DEBUG: [meter] pod not running, stop. pod_id={pod_id}")
                return
            
            user_id = pod.user_id
            per_minute = max(1, int(round(pod.hourly_rate_cents / 60)))
        
        # Atomic debit
        ok = _atomic_debit(user_id, per_minute)
        if not ok:
            print(f"DEBUG: [meter] credits depleted, stopping pod_id={pod_id}")
            teardown_pod(pod_id)
            return

def stop_pod(pod_id: int):
    """Stop a pod (pause the instance, don't terminate it)"""
    print(f"DEBUG: Starting pod stop for pod {pod_id}")
    
    # Keep session open for the entire function
    with Session(engine) as db:
        try:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return

            print(f"DEBUG: Found pod {pod_id} with status {pod.status}, instance_id: {pod.instance_id}")

            # Update status to stopping
            pod.status = 'stopping'
            db.commit()
            
            # If pod has no instance_id, it's already stopped
            if not pod.instance_id:
                print(f"DEBUG: Pod {pod_id} has no instance_id, marking as stopped")
                pod.status = 'stopped'
                pod.public_ip = None
                db.commit()
                logger.info(f"Pod {pod_id} marked as stopped (no instance to stop)")
                return
            
            # AWS EC2 stop logic (don't terminate!)
            logger.info(f"[stop] start pod_id={pod_id} instance_id={pod.instance_id}")
            
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Stop the EC2 instance (don't terminate!)
            print(f"DEBUG: Stopping instance {pod.instance_id}")
            ec2.stop_instances(InstanceIds=[pod.instance_id])
            
            # Wait for instance to be stopped
            print(f"DEBUG: Waiting for instance {pod.instance_id} to be stopped...")
            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(InstanceIds=[pod.instance_id], WaiterConfig={'MaxAttempts': 30, 'Delay': 10})
            
            print(f"DEBUG: Instance {pod.instance_id} stopped successfully")
            
            # Update pod status to stopped and clear public IP (but keep instance_id for restart)
            pod.status = 'stopped'
            pod.public_ip = None
            # Keep instance_id so we can restart later!
            db.commit()
            
            print(f"DEBUG: [stop] stopped pod_id={pod_id}")
            logger.info(f"Pod {pod_id} stopped successfully (instance preserved for restart)")
            
        except Exception as e:
            print(f"DEBUG: Error stopping pod {pod_id}: {e}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            # Set status to error
            try:
                pod.status = 'error'
                db.commit()
            except:
                # If pod variable doesn't exist, fetch it again
                pod = db.query(Pod).filter(Pod.id == pod_id).first()
                if pod:
                    pod.status = 'error'
                    db.commit()
            raise

def teardown_pod(pod_id: int):
    """Teardown/Delete a pod completely (terminate the instance)"""
    print(f"DEBUG: Starting pod teardown/deletion for pod {pod_id}")
    
    # Keep session open for the entire function
    with Session(engine) as db:
        try:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return

            print(f"DEBUG: Found pod {pod_id} with status {pod.status}, instance_id: {pod.instance_id}")

            # Update status to stopping (for delete process)
            pod.status = 'stopping'
            db.commit()
            
            # If pod has no instance_id, it's already cleaned up
            if not pod.instance_id:
                print(f"DEBUG: Pod {pod_id} has no instance_id, marking as stopped")
                pod.status = 'stopped'
                pod.public_ip = None
                db.commit()
                logger.info(f"Pod {pod_id} marked as stopped (no instance to terminate)")
                return
            
            # AWS EC2 termination logic (for delete)
            logger.info(f"[teardown] start pod_id={pod_id} instance_id={pod.instance_id}")
            
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Terminate the EC2 instance (destroy it completely)
            print(f"DEBUG: Terminating instance {pod.instance_id}")
            ec2.terminate_instances(InstanceIds=[pod.instance_id])
            
            # Wait for instance to be terminated
            print(f"DEBUG: Waiting for instance {pod.instance_id} to be terminated...")
            waiter = ec2.get_waiter("instance_terminated")
            waiter.wait(InstanceIds=[pod.instance_id], WaiterConfig={'MaxAttempts': 30, 'Delay': 10})
            
            print(f"DEBUG: Instance {pod.instance_id} terminated successfully")
            
            # Since this is called during deletion, remove the pod from database
            print(f"DEBUG: [teardown] removing pod {pod_id} from database after instance termination")
            db.delete(pod)
            db.commit()
            
            print(f"DEBUG: [teardown] terminated pod_id={pod_id}")
            logger.info(f"Pod {pod_id} torn down successfully (instance terminated and removed from database)")
            
        except Exception as e:
            print(f"DEBUG: Error tearing down pod {pod_id}: {e}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            # Set status to error
            try:
                pod.status = 'error'
                db.commit()
            except:
                # If pod variable doesn't exist, fetch it again
                pod = db.query(Pod).filter(Pod.id == pod_id).first()
                if pod:
                    pod.status = 'error'
                    db.commit()
            raise

def resize_filesystem(pod_id: int, volume_id: str, old_size_gb: int, new_size_gb: int):
    """Automatically resize the filesystem after EBS volume expansion"""
    print(f"DEBUG: Resizing filesystem for pod {pod_id}, volume {volume_id}")
    
    with Session(engine) as db:
        try:
            # Get pod from database
            pod = db.query(Pod).filter(Pod.id == pod_id).first()
            
            if not pod:
                logger.error(f"Pod {pod_id} not found in database")
                return
            
            if not pod.instance_id:
                logger.error(f"Pod {pod_id} has no instance_id, cannot resize filesystem")
                return

            logger.info(f"[resize_filesystem] pod_id={pod_id} volume_id={volume_id} {old_size_gb}GB -> {new_size_gb}GB")
            
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Wait for volume to be ready for filesystem operations
            print(f"DEBUG: Waiting for volume {volume_id} to be ready")
            waiter = ec2.get_waiter('volume_available')
            waiter.wait(VolumeIds=[volume_id])
            
            # Get instance details for SSH connection
            desc = ec2.describe_instances(InstanceIds=[pod.instance_id])
            if not desc["Reservations"]:
                logger.error(f"Instance {pod.instance_id} not found in AWS")
                return
                
            instance = desc["Reservations"][0]["Instances"][0]
            if instance["State"]["Name"] != "running":
                logger.info(f"Instance {pod.instance_id} is not running, filesystem resize will be done on next start")
                return

            # Use AWS Systems Manager to run resize commands
            ssm = boto3.client("ssm", region_name=settings.AWS_REGION,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

            # Determine the root device and filesystem type
            root_device = instance.get("RootDeviceName", "/dev/sda1")
            
            # Try to resize the filesystem (works for most Linux distributions)
            resize_commands = [
                "sudo growpart /dev/sda 1",  # Expand partition
                "sudo resize2fs /dev/sda1",  # Resize ext4 filesystem
                "sudo xfs_growfs /",         # Resize XFS filesystem (alternative)
            ]
            
            for cmd in resize_commands:
                try:
                    print(f"DEBUG: Running command: {cmd}")
                    response = ssm.send_command(
                        InstanceIds=[pod.instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={'commands': [cmd]},
                        TimeoutSeconds=300
                    )
                    
                    command_id = response['Command']['CommandId']
                    
                    # Wait for command completion
                    time.sleep(5)
                    output = ssm.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=pod.instance_id
                    )
                    
                    if output['Status'] == 'Success':
                        logger.info(f"Successfully ran {cmd} on pod {pod_id}")
                        break
                    else:
                        logger.warning(f"Command {cmd} failed on pod {pod_id}: {output.get('StandardErrorContent', 'Unknown error')}")
                        
                except Exception as e:
                    logger.warning(f"Failed to run {cmd} on pod {pod_id}: {e}")
                    continue
            
            logger.info(f"[resize_filesystem] Completed filesystem resize for pod {pod_id}")
            
        except Exception as e:
            logger.error(f"[resize_filesystem] Failed to resize filesystem for pod {pod_id}: {e}")
            traceback.print_exc()
