from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional
from apps.api.app.db import get_session
from apps.api.app.models import Pod, Credits, PodStatus, Provider
from apps.api.app.deps import current_user
from apps.api.app.catalog_aws import get_catalog, get_instance_by_id
from apps.api.app.queue import q

router = APIRouter(prefix="/v1/catalog", tags=["catalog"])

class LaunchInstanceIn(BaseModel):
    id: str

@router.get("/aws")
def list_aws_catalog(gpu_only: bool = Query(False, description="Filter to show only GPU instances")):
    """Get the AWS instance catalog with pricing and markup."""
    try:
        catalog = get_catalog(gpu_only=gpu_only)
        return catalog
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching catalog: {str(e)}")

@router.post("/aws/launch")
def launch_aws_instance(body: LaunchInstanceIn, session: Session = Depends(get_session), user=Depends(current_user)):
    """Launch an AWS instance from the catalog."""
    try:
        # Get instance details from catalog
        instance = get_instance_by_id(body.id)
        if not instance:
            raise HTTPException(status_code=400, detail="Invalid instance ID")
        
        # Calculate hourly rate in cents
        hourly_rate_cents = round(instance["price_with_markup_usd"] * 100)
        
        # Credit check: require at least 1 minute worth
        min_needed = max(1, round(hourly_rate_cents / 60))
        credits = session.query(Credits).filter(Credits.user_id == user.id).first()
        if not credits or credits.balance_cents < min_needed:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient credits. Need at least {min_needed} cents, have {credits.balance_cents if credits else 0}"
            )
        
        # Create pod record
        pod = Pod(
            user_id=user.id,
            status=PodStatus.pending,
            provider=Provider.aws,
            instance_type=instance["instance_type"],  # Set instance_type from catalog
            hourly_rate_cents=hourly_rate_cents,
        )
        session.add(pod)
        session.commit()
        session.refresh(pod)
        
        # Enqueue provisioning job
        job = q.enqueue("apps.api.workers.provisioner.provision_pod", pod.id, instance["instance_type"])
        print(f"enqueued job {job.id}")
        
        return {
            "id": pod.id, 
            "status": pod.status,
            "instance_type": instance["instance_type"],
            "hourly_rate_cents": hourly_rate_cents,
            "estimated_cost_per_minute": min_needed
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error launching instance: {str(e)}")
