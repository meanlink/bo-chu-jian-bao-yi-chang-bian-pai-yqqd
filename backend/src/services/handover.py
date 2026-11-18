"""交班现场封存。

交班点（cutoff）在登记时固定；封存只收录 cutoff 前已生效的数据批次、分析任务状态、
业务批准与已投递简报。cutoff 之后新建的行由 created_at 自然排除，之后结束的计算
按交班点还原为“计算中”，之后才批准的结论不计入。封存按阶段分批入库并记录游标，
中断后可从原交班点继续；唯一约束保证重试不会重复生成现场行。封存完成后写入现场
指纹，供事后核对；此后的补算与分发只写入新行，不回改旧现场。
"""
from datetime import datetime
import secrets
import time

from sqlalchemy import select, func

from src.models import (Dataset, Job, Report, Delivery, Handover,
                        HandoverDataset, HandoverJob, HandoverDelivery)
from src.services.audit import record
from src.utils.serialization import checksum

CHUNK_SIZE = 200
JOB_FINAL_STATES = ('completed', 'failed')


def _job_status_at(job, cutoff):
    """按交班点还原任务状态：交班后才结束的计算在交班时仍是计算中。"""
    if job.status in JOB_FINAL_STATES:
        if job.finished_at is None or job.finished_at <= cutoff:
            return job.status
        # 交班后才结束：交班时已开始则为计算中，尚未开始则仍排队。
        if job.started_at is not None and job.started_at > cutoff:
            return 'queued'
        return 'running'
    if job.status == 'running':
        # 旧数据缺少开始时间时，交班前已存在的运行任务按计算中归档。
        return 'running' if job.started_at is None or job.started_at <= cutoff else 'queued'
    return 'queued'


def _approval_at(job, cutoff):
    """返回交班时点已生效的批准时间；未生效返回 None。

    历史数据的批准时间缺失时，以任务完成时间作为批准生效的兜底时点；
    交班点之后的批准一律不计入。
    """
    if not job.approved:
        return None
    approved_at = job.approved_at
    if approved_at is None:
        approved_at = job.finished_at if job.finished_at is not None else job.created_at
    return approved_at if approved_at <= cutoff else None


def _scene_payload(h, datasets, jobs, deliveries):
    return {
        'ref': h.ref,
        'cutoff': h.cutoff,
        'datasets': [
            {'id': d.dataset_id, 'name': d.name, 'source': d.source,
             'checksum': d.checksum, 'rows': d.rows_count, 'created_at': d.created_at}
            for d in sorted(datasets, key=lambda row: row.dataset_id)
        ],
        'jobs': [
            {'id': j.job_id, 'name': j.name, 'dataset_id': j.dataset_id,
             'params': j.params, 'status': j.status, 'approved': bool(j.approved),
             'approved_at': j.approved_at, 'created_at': j.created_at,
             'started_at': j.started_at, 'finished_at': j.finished_at}
            for j in sorted(jobs, key=lambda row: row.job_id)
        ],
        'deliveries': [
            {'id': d.delivery_id, 'report_id': d.report_id, 'report': d.report_name,
             'job_id': d.job_id, 'checksum': d.checksum, 'filename': d.filename,
             'destination': d.destination, 'created_at': d.created_at}
            for d in sorted(deliveries, key=lambda row: row.delivery_id)
        ],
    }


def done_counts(db, h):
    return {
        'datasets': db.scalar(select(func.count()).select_from(HandoverDataset)
                              .where(HandoverDataset.handover_id == h.id)) or 0,
        'jobs': db.scalar(select(func.count()).select_from(HandoverJob)
                          .where(HandoverJob.handover_id == h.id)) or 0,
        'deliveries': db.scalar(select(func.count()).select_from(HandoverDelivery)
                                .where(HandoverDelivery.handover_id == h.id)) or 0,
    }


def create(db, label, user):
    now = time.time()
    cutoff = now
    h = Handover(
        ref=f'HO-{datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S")}-{secrets.token_hex(2)}',
        label=label.strip() or f'交班 {datetime.fromtimestamp(now).strftime("%m-%d %H:%M")}',
        cutoff=cutoff, status='pending', phase='datasets', cursor=0,
        dataset_total=db.scalar(select(func.count()).select_from(Dataset)
                                .where(Dataset.created_at <= cutoff)) or 0,
        job_total=db.scalar(select(func.count()).select_from(Job)
                            .where(Job.created_at <= cutoff)) or 0,
        delivery_total=db.scalar(select(func.count()).select_from(Delivery)
                                 .where(Delivery.created_at <= cutoff)) or 0,
        created_by=user.id, created_at=now,
    )
    db.add(h)
    db.flush()
    record(db, user.email, 'handover.create', {'id': h.id, 'ref': h.ref, 'cutoff': cutoff})
    return h


def resume(db, h, user):
    """中断后从原交班点继续；已完成现场原样返回，不重复生成。"""
    if h.status == 'completed':
        record(db, user.email, 'handover.resume_noop', {'id': h.id})
        return h
    h.status = 'pending'
    h.error = ''
    record(db, user.email, 'handover.resume', {'id': h.id, 'phase': h.phase, 'cursor': h.cursor})
    return h


def _insert_missing(db, model, key, rows, handover_id):
    if not rows:
        return
    ids = [getattr(row, key) for row in rows]
    existing = set(db.scalars(select(getattr(model, key))
                              .where(model.handover_id == handover_id,
                                     getattr(model, key).in_(ids))).all())
    for row in rows:
        if getattr(row, key) not in existing:
            db.add(row)


def _reconcile(db, h):
    """收尾对账：若并发写入在分批之间提交了 created_at<=cutoff 的行，
    以库里符合条件的行数重新从游标 0 扫描补齐（唯一约束保证幂等）。"""
    expected = {
        'datasets': db.scalar(select(func.count()).select_from(Dataset)
                              .where(Dataset.created_at <= h.cutoff)) or 0,
        'jobs': db.scalar(select(func.count()).select_from(Job)
                          .where(Job.created_at <= h.cutoff)) or 0,
        'deliveries': db.scalar(select(func.count()).select_from(Delivery)
                                .where(Delivery.created_at <= h.cutoff)) or 0,
    }
    archived = done_counts(db, h)
    for phase in ('datasets', 'jobs', 'deliveries'):
        if archived[phase] < expected[phase]:
            h.phase, h.cursor = phase, 0
            return True
    return False


def advance(db, h, limit_chunks=6):
    """推进封存；每个阶段按 id 顺序分批，游标随批提交，可从断点继续。

    进入新阶段前重置游标，因此单批较大或中断后重试都能重新扫过漏行；
    归档唯一约束保证插入幂等。阶段全部走完后做一次对账扫描，再把现场置为完成。
    """
    h.status = 'running'
    db.commit()
    chunks = 0
    reconciles = 0
    while chunks < limit_chunks:
        h = db.get(Handover, h.id)
        if h is None or h.status == 'completed':
            return h
        if h.phase == 'datasets':
            rows = list(db.scalars(select(Dataset)
                                   .where(Dataset.id > h.cursor,
                                          Dataset.created_at <= h.cutoff)
                                   .order_by(Dataset.id).limit(CHUNK_SIZE)))
            if rows:
                _insert_missing(db, HandoverDataset, 'dataset_id', [
                    HandoverDataset(handover_id=h.id, dataset_id=d.id, name=d.name,
                                    source=d.source, checksum=d.checksum,
                                    rows_count=len(d.records), created_at=d.created_at)
                    for d in rows], h.id)
                h.cursor = rows[-1].id
            else:
                h.phase, h.cursor = 'jobs', 0
            db.commit()
            chunks += 1
        elif h.phase == 'jobs':
            rows = list(db.scalars(select(Job)
                                   .where(Job.id > h.cursor,
                                          Job.created_at <= h.cutoff)
                                   .order_by(Job.id).limit(CHUNK_SIZE)))
            if rows:
                names = dict(db.execute(select(Dataset.id, Dataset.name)).all())
                snapshots = []
                for j in rows:
                    approval_at = _approval_at(j, h.cutoff)
                    snapshots.append(HandoverJob(
                        handover_id=h.id, job_id=j.id, name=j.name,
                        dataset_id=j.dataset_id, dataset_name=names.get(j.dataset_id, ''),
                        params=j.params or {}, status=_job_status_at(j, h.cutoff),
                        approved=approval_at is not None, approved_at=approval_at,
                        created_at=j.created_at,
                        started_at=(j.started_at if j.started_at is not None
                                    and j.started_at <= h.cutoff else None),
                        finished_at=(j.finished_at if j.finished_at is not None
                                     and j.finished_at <= h.cutoff else None),
                    ))
                _insert_missing(db, HandoverJob, 'job_id', snapshots, h.id)
                h.cursor = rows[-1].id
            else:
                h.phase, h.cursor = 'deliveries', 0
            db.commit()
            chunks += 1
        elif h.phase == 'deliveries':
            rows = list(db.scalars(select(Delivery)
                                   .where(Delivery.id > h.cursor,
                                          Delivery.created_at <= h.cutoff)
                                   .order_by(Delivery.id).limit(CHUNK_SIZE)))
            if rows:
                reports = {r.id: r for r in db.scalars(select(Report)).all()}
                jobs = {j.id: j for j in db.scalars(select(Job)).all()}
                datasets = {d.id: d for d in db.scalars(select(Dataset)).all()}
                _insert_missing(db, HandoverDelivery, 'delivery_id', [
                    _delivery_snapshot(h, d, reports, jobs, datasets) for d in rows], h.id)
                h.cursor = rows[-1].id
            else:
                h.phase = 'done'
            db.commit()
            chunks += 1
        elif reconciles < 2:
            reconciles += 1
            if _reconcile(db, h):
                db.commit()
                chunks += 1
                continue
            break
        else:
            break
    h = db.get(Handover, h.id)
    if h is not None and h.status != 'completed' and h.phase == 'done':
        _complete(db, h)
    db.commit()
    return h


def _delivery_snapshot(h, delivery, reports, jobs, datasets):
    report = reports.get(delivery.report_id)
    job = jobs.get(report.job_id) if report else None
    dataset = datasets.get(job.dataset_id) if job else None
    return HandoverDelivery(
        handover_id=h.id, delivery_id=delivery.id, report_id=delivery.report_id,
        report_name=report.name if report else '',
        job_id=report.job_id if report else 0,
        job_name=job.name if job else '',
        dataset_id=job.dataset_id if job else 0,
        dataset_name=dataset.name if dataset else '',
        dataset_checksum=dataset.checksum if dataset else '',
        checksum=delivery.checksum, filename=delivery.filename,
        destination=delivery.destination, created_at=delivery.created_at,
    )


def _complete(db, h):
    datasets = list(db.scalars(select(HandoverDataset)
                               .where(HandoverDataset.handover_id == h.id)))
    jobs = list(db.scalars(select(HandoverJob).where(HandoverJob.handover_id == h.id)))
    deliveries = list(db.scalars(select(HandoverDelivery)
                                 .where(HandoverDelivery.handover_id == h.id)))
    h.dataset_total, h.job_total, h.delivery_total = len(datasets), len(jobs), len(deliveries)
    h.scene_checksum = checksum(_scene_payload(h, datasets, jobs, deliveries))
    h.status = 'completed'
    h.completed_at = time.time()
    record(db, 'worker', 'handover.completed',
           {'id': h.id, 'checksum': h.scene_checksum,
            'datasets': len(datasets), 'jobs': len(jobs), 'deliveries': len(deliveries)})


def verify(db, h):
    """按归档行重算现场指纹，确认现场未被后来的补算或分发改写。"""
    if h.status != 'completed' or not h.scene_checksum:
        return False
    datasets = list(db.scalars(select(HandoverDataset)
                               .where(HandoverDataset.handover_id == h.id)))
    jobs = list(db.scalars(select(HandoverJob).where(HandoverJob.handover_id == h.id)))
    deliveries = list(db.scalars(select(HandoverDelivery)
                                 .where(HandoverDelivery.handover_id == h.id)))
    return checksum(_scene_payload(h, datasets, jobs, deliveries)) == h.scene_checksum
