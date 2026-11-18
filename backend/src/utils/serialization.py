import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}

def handover_dict(h, done):
    totals={'datasets':h.dataset_total,'jobs':h.job_total,'deliveries':h.delivery_total}
    if not sum(totals.values()):
        percent=100 if h.status=='completed' else 0
    else:
        percent=round(sum(min(done[k],totals[k]) for k in totals)/sum(totals.values())*100,1)
    progress={'totals':totals,'done':done,'percent':percent}
    return {'id':h.id,'ref':h.ref,'label':h.label,'cutoff':h.cutoff,'status':h.status,'phase':h.phase,
            'cursor':h.cursor,'created_at':h.created_at,'completed_at':h.completed_at,
            'scene_checksum':h.scene_checksum,'error':h.error,'progress':progress}

def handover_dataset_dict(x):
    return {'dataset_id':x.dataset_id,'name':x.name,'source':x.source,'checksum':x.checksum,'rows':x.rows_count,'created_at':x.created_at}

def handover_job_dict(x):
    return {'job_id':x.job_id,'name':x.name,'dataset_id':x.dataset_id,'dataset_name':x.dataset_name,'params':x.params,
            'status':x.status,'approved':x.approved,'approved_at':x.approved_at,'created_at':x.created_at,
            'started_at':x.started_at,'finished_at':x.finished_at}

def handover_delivery_dict(x):
    return {'delivery_id':x.delivery_id,'report_id':x.report_id,'report_name':x.report_name,'job_id':x.job_id,
            'job_name':x.job_name,'dataset_id':x.dataset_id,'dataset_name':x.dataset_name,
            'dataset_checksum':x.dataset_checksum,'checksum':x.checksum,'filename':x.filename,
            'destination':x.destination,'created_at':x.created_at}
