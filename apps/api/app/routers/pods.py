from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from apps.api.app.db import get_session
from apps.api.app.models import Pod, Credits, PodStatus, Provider
from apps.api.app.deps import current_user
from apps.api.app.templates import TEMPLATES
from apps.api.app.queue import q
router = APIRouter(prefix="/v1", tags=["pods"])

class CreatePodIn(BaseModel):
    template_id: str

@router.get("/templates")
def list_templates():
    return [{"id": k, **v} for k, v in TEMPLATES.items()]

@router.post("/pods")
def create_pod(body: CreatePodIn, session: Session = Depends(get_session), user=Depends(current_user)):
    tpl = TEMPLATES.get(body.template_id)
    if not tpl:
        raise HTTPException(status_code=400, detail="unknown template")
    # credit check: at least 1 min worth
    min_needed = tpl["hourly_rate_cents"] // 60 or 1
    credits = session.exec(select(Credits).where(Credits.user_id == user.id)).first()
    if not credits or credits.balance_cents < min_needed:
        raise HTTPException(status_code=402, detail="insufficient credits")

    pod = Pod(
        user_id=user.id,
        status=PodStatus.pending,
        provider=Provider.aws,
        hourly_rate_cents=tpl["hourly_rate_cents"],
    )
    session.add(pod); session.commit(); session.refresh(pod)

    # enqueue real provisioner (string import path)
    job = q.enqueue("apps.api.workers.provisioner.provision_pod", pod.id, tpl["instance_type"])
    print("enqueued job", job.id)  # or log it
    return {"id": pod.id, "status": pod.status}

@router.get("/pods")
def list_pods(session: Session = Depends(get_session), user=Depends(current_user)):
    rows = session.exec(select(Pod).where(Pod.user_id == user.id).order_by(Pod.id.desc())).all()
    return [
        {
            "id": p.id,
            "status": p.status,
            "public_ip": p.public_ip,
            "template": None,  # we'll store template later if needed
            "hourly_rate_cents": p.hourly_rate_cents,
            "instance_id": p.instance_id,
        }
        for p in rows
    ]

@router.post("/pods/{pod_id}/stop")
def stop_pod(pod_id: int, session: Session = Depends(get_session), user=Depends(current_user)):
    pod = session.get(Pod, pod_id)
    if not pod or pod.user_id != user.id:
        raise HTTPException(status_code=404, detail="pod not found")
    if pod.status in (PodStatus.stopping, PodStatus.stopped):
        return {"id": pod.id, "status": pod.status}
    # enqueue teardown by string
    q.enqueue("apps.api.workers.provisioner.teardown_pod", pod.id)
    pod.status = PodStatus.stopping
    session.add(pod); session.commit()
    return {"id": pod.id, "status": str(pod.status)}
