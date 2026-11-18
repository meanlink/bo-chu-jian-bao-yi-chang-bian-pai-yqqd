import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report, Handover
from src.services.business import analyze
from src.services.reports import deliver
from src.services import handover
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        j.status='running'; j.started_at=j.started_at or time.time(); db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            result=analyze(d.records,j.params)
            json.dumps(result,allow_nan=False)
            j.result=result;j.status='completed';j.finished_at=time.time()
            record(db,'worker','job.completed',{'id':j.id})
        except Exception as e:
            logging.exception('Analysis failed')
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def tick():
    with Session() as db:
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
    seal_pending()

def seal_pending():
    """封存在 worker 内分批推进；中断后按原交班点游标继续。"""
    with Session() as db:
        ids=list(db.scalars(select(Handover.id).where(Handover.status.in_(('pending','running'))).order_by(Handover.id).limit(3)))
    for handover_id in ids:
        with Session() as db:
            h=db.get(Handover,handover_id)
            if not h or h.status=='completed':continue
            try:
                handover.advance(db,h)
            except Exception as exc:
                logging.exception('Handover sealing failed')
                db.rollback()
                h=db.get(Handover,handover_id)
                if h and h.status!='completed':
                    h.status='failed';h.error=str(exc)[:990]
                    record(db,'worker','handover.failed',{'id':h.id,'error':h.error})
                    db.commit()
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            j.status='queued';record(db,'worker','job.recovered',{'id':j.id})
        db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=r.blpop('analysis:queue',timeout=1)
            if item:execute(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry');time.sleep(2)
if __name__=='__main__':main()
