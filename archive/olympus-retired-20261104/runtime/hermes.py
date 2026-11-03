"""Project durable runtime facts through the existing Hermes reporter."""
from pathlib import Path
from datetime import datetime
import hashlib,json,runpy
from contextlib import closing

def export(root,state,task,agent,events):
    reporter=runpy.run_path(str(root/'tools/hermes-report.py'))
    ledger=runpy.run_path(str(root/'agents/hermes/scripts/ledger.py'))
    db=state/'hermes.sqlite';outbox=state/'outbox.sqlite'
    if not db.exists():ledger['initialize'](db)
    tenant=task['tenant_id'];prefix=hashlib.sha256((tenant+'\0'+task['id']).encode()).hexdigest()[:24]
    rid=lambda x:prefix+':'+x
    start=events[0]['time'];source=rid('source');snapshot='runtime-agent:'+hashlib.sha256((agent['id']+agent['version']+hashlib.sha256((root/agent['entry']).read_bytes()).hexdigest()).encode()).hexdigest();request=rid('request')
    ctx={'request_ref':request,'primary_agent_ref':snapshot,'related_agent_refs':[],
         'work_items':task['work_items'],'linkage_state':'partial','linkage_note':'Only events through this runtime are observed; external dialogue and corrections require explicit submission.'}
    def record(key,kind,payload,context=True,refs=None,time=None):
        r={'schema_version':2,'record_id':rid(key),'tenant_id':tenant,'kind':kind,'created_at':time or start,'evidence_refs':refs if refs is not None else [source],'payload':payload}
        if context:r['context']=ctx
        return r
    def event(key,kind,payload,refs=None,time=None):
        return record(key,kind,{'source_key':prefix,'event_key':rid(key),'source_revision':'1',**payload},refs=refs,time=time)
    records=[record('source','source',{'source_key':prefix,'authority_ref':task['authority_ref'],'purpose':'authorized runtime execution telemetry','retention':task['retention'],'allowed_fields':['runtime_events','usage','artifact_refs']},False,[]),
        record('agent','agent_snapshot',{'agent_id':agent['id'],'version':agent['version'],'definition_digest':hashlib.sha256((root/agent['entry']).read_bytes()).hexdigest(),'definition_ref':agent['entry'],'origin':'registered','role_kind':'subagent'},False),
        event('request','request',{'request_key':task['id'],'project_id':task['project_id'],'initiated_at':start,'intent':task['outcome']})]
    records[1]['record_id']=snapshot
    with closing(ledger['connect'](db)) as cx:
        existing=cx.execute('SELECT 1 FROM records WHERE tenant=? AND id=?',(tenant,snapshot)).fetchone()
        if existing:records[1]=ledger['load_record'](cx,tenant,snapshot)
    records.append(event('user','message',{'conversation_id':task['id'],'message_id':rid('user'),'turn_id':rid('turn'),'role':'user','visibility':'user_visible','content_ref':'runtime.sqlite#'+task['id']+'/task','step_ref':None,'occurred_at':start}))
    failures={e['data']['call']:e for e in events if e['kind']=='validation_failure'}
    accepted={e['data']['call'] for e in events if e['kind'] in {'step_result','tool_result'}}
    interrupted={e['data']['call'] for e in events if e['kind']=='validation_interrupted'}
    for e in events:
        if e['kind']!='call_end':continue
        d=e['data'];key='call-'+str(d['call']);p=d['profile'];u=d.get('usage') or {}
        usage={'scope':'exclusive','usage_key':rid(key),'provider':p['protocol'],'model':p['model'],'metering_ref':'runtime.sqlite#'+task['id']+'/'+str(e['seq']),'equivalents':[]}
        for k in ['input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens','reasoning_output_tokens']:
            value=u.get(k);usage[k]={'value':value,'status':'measured' if value is not None else 'unavailable','reason':'provider response' if value is not None else 'not supplied or outcome unknown','method':'provider reported count'}
        duration=(datetime.fromisoformat(e['time'])-datetime.fromisoformat(d['started_at'])).total_seconds()*1000
        if d['status']=='received' and d['call'] not in accepted and d['call'] not in failures and d['call'] not in interrupted:continue # validation not durably resolved yet
        records.append(event(key,'step',{'step_key':rid(key),'phase':d['step_id'],'started_at':d['started_at'],'ended_at':e['time'],'duration_ms':duration,'status':'succeeded' if d['call'] in accepted else 'failed','attempt':d['call'],'trace_id':hashlib.sha256(task['id'].encode()).hexdigest()[:32],'span_id':hashlib.sha256(key.encode()).hexdigest()[:16],'parent_step_ref':None,'usage':usage},time=e['time']))
        if 'text' in d:records.append(event(key+'-message','message',{'conversation_id':task['id'],'message_id':rid(key+'-message'),'turn_id':rid('turn'),'role':'assistant','visibility':'internal','content_ref':'runtime.sqlite#'+task['id']+'/'+str(e['seq']),'step_ref':rid(key),'occurred_at':e['time']},[source,rid(key)],e['time']))
        if d['call'] in failures:
            failure=failures[d['call']]
            records.append(event(key+'-issue','quality_issue',{'issue_id':rid(key+'-issue'),'issue_ref':'runtime.sqlite#'+task['id']+'/'+str(failure['seq']),'severity':'output_contract','step_ref':rid(key),'occurred_at':failure['time']},[source,rid(key)],failure['time']))
        previous=[f for n,f in failures.items() if n<d['call'] and f['data']['step_id']==d['step_id']]
        if previous:
            previous=max(previous,key=lambda f:f['data']['call']);issue=rid('call-'+str(previous['data']['call'])+'-issue')
            records.append(event(key+'-rework','rework',{'issue_ref':issue,'action':'retry rejected output under existing task budget','step_ref':rid(key),'occurred_at':e['time']},[source,rid(key),issue],e['time']))
    terminal=next((e for e in events if e['kind']=='completed' or (e['kind']=='operator_reconciliation' and e['data']['decision']=='cancel')),None)
    if terminal:records.append(event('end','request_end',{'status':'completed' if terminal['kind']=='completed' else 'cancelled','occurred_at':terminal['time']},time=terminal['time']))
    for category in ['messages','steps','directions','quality','usage']:
        records.append(event('coverage-'+category,'coverage',{'category':category,'state':'partial' if category!='directions' else 'unavailable','observed':None,'expected':None,'reason':'Only this runtime observed; external conversations, semantic corrections and business validation are not inferred','window_start':start,'window_end':start}))
    # Skill invocations belong to the same actual Agent; each call is metered once.
    step_skills={s['id']:s.get('skill') for s in task['steps']}
    call_skills={r['record_id']:step_skills.get(r['payload']['phase']) for r in records if r['kind']=='step'}
    buckets={('agent',agent['id']):[]}
    for r in records:
        skill=call_skills.get(r['record_id']) if r['kind']=='step' else call_skills.get(r['payload'].get('step_ref'))
        owner=('skill',skill) if skill else ('agent',agent['id'])
        buckets.setdefault(owner,[]).append(r)
    binding={'template':False,'tenant_id':tenant,'source_ref':source,'agent_snapshot_ref':snapshot,'request_ref':request,'outbox_path':str(outbox.resolve()),'sink_ref':str(db.resolve()),'authority_ref':task['authority_ref']}
    for (kind,cid),batch_records in buckets.items():
        if not batch_records:continue
        batch=hashlib.sha256(reporter['canonical'](batch_records).encode()).hexdigest()
        queued=reporter['enqueue'](root,outbox,tenant,batch,batch_records,binding,kind=kind,cid=cid)
        reporter['flush'](root,outbox,db)
        receipt=next(r for r in reporter['status'](outbox,tenant) if r['submission_id']==queued['submission_id'])
        if receipt['status']!='sent':raise ValueError('Hermes delivery pending: '+str(receipt['last_error']))
    return receipt
