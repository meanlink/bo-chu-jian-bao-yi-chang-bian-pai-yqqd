from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Handover, HandoverDataset, HandoverJob, HandoverDelivery
from src.schemas.handover import HandoverInput
from src.middlewares.auth import current_user, can_write
from src.services import handover
from src.services.audit import record
from src.utils.serialization import (handover_dict, handover_dataset_dict,
                                     handover_job_dict, handover_delivery_dict)
router=APIRouter(prefix='/handovers')

def _detail(db,h):
    datasets=[handover_dataset_dict(x) for x in db.scalars(select(HandoverDataset).where(HandoverDataset.handover_id==h.id).order_by(HandoverDataset.dataset_id))]
    jobs=[handover_job_dict(x) for x in db.scalars(select(HandoverJob).where(HandoverJob.handover_id==h.id).order_by(HandoverJob.job_id))]
    deliveries=[handover_delivery_dict(x) for x in db.scalars(select(HandoverDelivery).where(HandoverDelivery.handover_id==h.id).order_by(HandoverDelivery.delivery_id))]
    return {**handover_dict(h,handover.done_counts(db,h)),'datasets':datasets,'jobs':jobs,'deliveries':deliveries,'verified':handover.verify(db,h)}

@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    rows=list(db.scalars(select(Handover).order_by(Handover.id.desc()).limit(100)))
    return [handover_dict(h,handover.done_counts(db,h)) for h in rows]

@router.post('',status_code=201)
def create(data:HandoverInput,db=Depends(get_db),u=Depends(can_write)):
    h=handover.create(db,data.label,u)
    db.commit(); return handover_dict(h,{'datasets':0,'jobs':0,'deliveries':0})

@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    h=db.get(Handover,id)
    if not h: raise HTTPException(404,'交班现场不存在')
    return _detail(db,h)

@router.post('/{id}/verify')
def verify(id:int,db=Depends(get_db),u=Depends(current_user)):
    h=db.get(Handover,id)
    if not h: raise HTTPException(404,'交班现场不存在')
    if h.status!='completed': raise HTTPException(409,'现场仍在封存，完成后才能核对指纹')
    ok=handover.verify(db,h)
    record(db,u.email,'handover.verify',{'id':id,'ok':ok});db.commit()
    return {'id':id,'ref':h.ref,'checksum':h.scene_checksum,'verified':ok}

@router.post('/{id}/resume')
def resume(id:int,db=Depends(get_db),u=Depends(can_write)):
    h=db.get(Handover,id)
    if not h: raise HTTPException(404,'交班现场不存在')
    handover.resume(db,h,u);db.commit()
    return handover_dict(h,handover.done_counts(db,h))
