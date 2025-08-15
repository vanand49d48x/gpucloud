import time, logging, traceback
import boto3
from botocore.exceptions import ClientError

from sqlmodel import Session, text
from apps.api.app.db import engine
from apps.api.app.models import Pod, PodStatus, Provider
from apps.api.app.config import settings

log = logging.getLogger("provisioner")
logging.basicConfig(level=logging.INFO)

def _update(pod_id, **fields):
    with Session(engine) as s:
        pod = s.get(Pod, pod_id)
        if not pod:
            return None
        for k, v in fields.items():
            setattr(pod, k, v)
        s.add(pod); s.commit(); s.refresh(pod)
        return pod

def _atomic_debit(user_id: int, cents: int) -> bool:
    # Returns True if debit succeeded, False if insufficient funds.
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                UPDATE credits
                SET balance_cents = balance_cents - :c
                WHERE user_id = :u AND balance_cents >= :c
                RETURNING balance_cents
            """),
            {"u": user_id, "c": cents}
        )
        conn.commit()
        return res.fetchone() is not None

def provision_pod(pod_id: int, instance_type: str = "t3.micro"):
    log.info(f"[provision] start pod_id={pod_id}")
    try:
        pod = _update(pod_id, status=PodStatus.starting)
        if not pod:
            return

        ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)

        # Launch
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
        _update(pod_id, instance_id=instance_id)

        # Wait until running, then fetch PublicIpAddress
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        desc = ec2.describe_instances(InstanceIds=[instance_id])
        inst = desc["Reservations"][0]["Instances"][0]
        public_ip = inst.get("PublicIpAddress")

        if not public_ip:
            # associate public IP if subnet isn't auto-assigning (belt & suspenders)
            # You can skip this if your subnet has MapPublicIpOnLaunch = true.
            log.warning("[provision] instance has no PublicIpAddress")

        _update(pod_id, public_ip=public_ip, status=PodStatus.running, provider=Provider.aws)
        log.info(f"[provision] running pod_id={pod_id} ip={public_ip} id={instance_id}")

        # Kick off a simple metering loop (blocks this worker job). For MVP this is fine.
        _meter_until_stopped(pod_id)

    except ClientError as e:
        log.error(f"[provision] AWS error: {e}")
        _update(pod_id, status=PodStatus.error)
    except Exception:
        log.error("[provision] failed\n" + traceback.format_exc())
        _update(pod_id, status=PodStatus.error)

def _meter_until_stopped(pod_id: int):
    """
    MVP metering: every 60s, charge per-minute based on hourly_rate_cents.
    Stops when pod.status != running or credits run out.
    """
    log.info(f"[meter] start pod_id={pod_id}")
    while True:
        time.sleep(60)

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
    log.info(f"[teardown] start pod_id={pod_id}")
    try:
        # Read instance id first
        with Session(engine) as s:
            pod = s.get(Pod, pod_id)
            if not pod:
                return
            instance_id = pod.instance_id

        if instance_id:
            ec2 = boto3.client("ec2", region_name=settings.AWS_REGION)
            try:
                ec2.terminate_instances(InstanceIds=[instance_id])
            except ClientError as ce:
                log.warning(f"[teardown] terminate_instances: {ce}")

        _update(pod_id, status=PodStatus.stopped)
        log.info(f"[teardown] done pod_id={pod_id}")
    except Exception:
        log.error("[teardown] failed\n" + traceback.format_exc())
        _update(pod_id, status=PodStatus.error)
