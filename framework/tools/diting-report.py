"""Shared local Diting reporter: durable queue, idempotent delivery and real receipts. No network."""
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json,runpy,sqlite3,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
DEPENDENCIES=['contracts/diting-reporting.json','tools/reporting.mjs','tools/diting-report.py','agents/diting/scripts/ledger.py','agents/diting/scripts/telemetry.py','agents/diting/references/data-contract.md','agents/diting/references/telemetry.md']
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(x).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def inside(root,relative):
    if not isinstance(relative,str) or Path(relative).is_absolute():raise ValueError('Expected component-relative path')
    p=(Path(root)/relative).resolve();p.relative_to(Path(root).resolve());return p
def make_profile(root,owner,component):
    policy=read(root/'contracts/diting-reporting.json')
    return {'schema_version':1,'component':{**{k:component[k] for k in ('kind','id','version','entry')},'entry_sha256':digest(inside(owner,component['entry']).read_bytes())},'required':True,'policy':'contracts/diting-reporting.json','policy_id':policy['policy_id'],'reporter':'tools/diting-report.py','events':policy['events'],'runtime_binding':'host_required','runtime_connected':False,'dependencies':{p:digest(inside(root,p).read_bytes()) for p in DEPENDENCIES}}
def check(root,owner):
    result=subprocess.run(['node',str(root/'tools/reporting.mjs'),'--component',str(root),str(owner)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise ValueError(result.stderr.strip())
    return json.loads(result.stdout)
def check_registered(root,kind,cid):
    m=read(root/'framework-manifest.json')
    items=m['agents'] if kind=='agent' else [*m['skills'],m['upstream_skill_reporting']]
    matches=[x for x in items if x.get('id',x.get('name'))==cid]
    if len(matches)!=1:raise ValueError('Component not uniquely registered')
    # All registered profiles are validated with the same validator as context loading.
    result=subprocess.run(['node',str(root/'tools/reporting.mjs'),'--all',str(root)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise ValueError(result.stderr.strip())
    return read(root/matches[0]['reporting'])
def validate_binding(root,binding,tenant,outbox):
    policy=read(root/'contracts/diting-reporting.json')
    if not isinstance(binding,dict) or binding.get('template') is not False:raise ValueError('Actual host binding required; template is not a binding')
    for field in policy['binding_fields']:
        if not isinstance(binding.get(field),str) or not binding[field].strip():raise ValueError('Missing host reporting binding: '+field)
    if binding['tenant_id']!=tenant or Path(binding['outbox_path']).resolve()!=Path(outbox).resolve():raise ValueError('Reporting binding tenant/outbox mismatch')
    if not Path(binding['sink_ref']).is_absolute():raise ValueError('Local reporter needs absolute ledger path as sink_ref')
def validate_bound_records(api,db,tenant,records,binding,component):
    supplied={r['record_id']:r for r in records}
    with closing(api['connect'](db)) as cx:
        def get(rid):return supplied[rid] if rid in supplied else api['load_record'](cx,tenant,rid)
        for field,kind in [('source_ref','source'),('agent_snapshot_ref','agent_snapshot'),('request_ref','request')]:
            if get(binding[field])['kind']!=kind:raise ValueError('Invalid bound record kind: '+field)
        source_key=get(binding['source_ref'])['payload']['source_key']
        agent=get(binding['agent_snapshot_ref'])['payload']
        if component['kind']=='agent' and (agent['agent_id']!=component['id'] or agent['version']!=component['version'] or agent['definition_digest']!=component['entry_sha256']):raise ValueError('Reporting Agent differs from the bound definition snapshot')
        for record in records:
            if record['kind'] in {'source','agent_snapshot'}:continue
            ctx=record.get('context',{})
            if ctx.get('request_ref')!=binding['request_ref'] or ctx.get('primary_agent_ref')!=binding['agent_snapshot_ref']:raise ValueError('Record outside host-bound request/Agent')
            if 'source_key' in record['payload'] and record['payload']['source_key']!=source_key:raise ValueError('Event source differs from host binding')
def connect(outbox):
    cx=sqlite3.connect(outbox,timeout=10)
    try:
        cx.execute('PRAGMA journal_mode=WAL')
        cx.execute('BEGIN IMMEDIATE')
        version=cx.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0,1,2):raise ValueError('Unsupported outbox schema')
        cx.execute('''CREATE TABLE IF NOT EXISTS submissions(
          id TEXT PRIMARY KEY,tenant TEXT NOT NULL,batch_key TEXT NOT NULL,
          digest TEXT NOT NULL,payload TEXT NOT NULL,profile TEXT NOT NULL,binding TEXT NOT NULL,
          owner TEXT,component_kind TEXT,component_id TEXT,
          status TEXT NOT NULL CHECK(status IN ('pending','sent')),
          queued_at TEXT NOT NULL,delivered_at TEXT,receipt TEXT,last_error TEXT)''')
        if 'last_attempt_seq' not in {r[1] for r in cx.execute('PRAGMA table_info(submissions)')}:
            cx.execute('ALTER TABLE submissions ADD COLUMN last_attempt_seq INTEGER NOT NULL DEFAULT 0')
        cx.execute('PRAGMA user_version=2');cx.commit();return cx
    except Exception:cx.close();raise
def enqueue(root,outbox,tenant,batch_key,records,binding,owner=None,kind=None,cid=None):
    if not tenant.strip() or not batch_key.strip() or not isinstance(records,list) or not records:raise ValueError('Tenant, stable batch key and nonempty records required')
    validate_binding(root,binding,tenant,outbox)
    profile=check(root,owner) if owner else check_registered(root,kind,cid)
    # The emitter adds only the reporting component to owned steps; shared request/source records remain identical across components.
    data=json.loads(canonical(records));component=profile['component']
    for r in data:
        if r.get('tenant_id')!=tenant or r.get('schema_version')!=2:raise ValueError('Tenant/schema mismatch')
        if r.get('kind')=='step':
            prior=r['payload'].get('reporting_component')
            if prior is not None and prior!=component:raise ValueError('Step belongs to another reporting component')
            r['payload']['reporting_component']=component
    payload=canonical(data);payload_hash=digest(payload.encode())
    sid=digest(canonical([tenant,component['kind'],component['id'],component['version'],batch_key]).encode())
    with closing(connect(outbox)) as cx:
        cx.execute('BEGIN IMMEDIATE')
        previous=cx.execute('SELECT digest,profile,binding,status FROM submissions WHERE id=?',(sid,)).fetchone()
        if previous:
            if previous[:3]!=(payload_hash,canonical(profile),canonical(binding)):raise ValueError('Batch key reused with different records, binding or component version')
            return {'submission_id':sid,'status':previous[3],'replayed':True,'delivered':previous[3]=='sent'}
        cx.execute('INSERT INTO submissions(id,tenant,batch_key,digest,payload,profile,binding,owner,component_kind,component_id,status,queued_at,delivered_at,receipt,last_error) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,tenant,batch_key,payload_hash,payload,canonical(profile),canonical(binding),str(Path(owner).resolve()) if owner else None,kind,cid,'pending',now(),None,None,None))
        cx.commit()
    return {'submission_id':sid,'status':'pending','delivered':False}
def flush(root,outbox,ledger_db,limit=100):
    if limit<1 or limit>1000:raise ValueError('Limit must be 1..1000')
    api=runpy.run_path(str(root/'agents/diting/scripts/ledger.py'))
    results=[]
    with closing(connect(outbox)) as cx:
        ids=[r[0] for r in cx.execute('SELECT id FROM submissions WHERE status=? ORDER BY last_attempt_seq,rowid LIMIT ?',('pending',limit))]
        for sid in ids:
            cx.execute('BEGIN IMMEDIATE')
            row=cx.execute('SELECT tenant,payload,profile,owner,component_kind,component_id,status,digest,binding FROM submissions WHERE id=?',(sid,)).fetchone()
            if row[6]=='sent':cx.rollback();continue
            # Rotate failed batches behind less recently attempted work; never discard them.
            cx.execute('UPDATE submissions SET last_attempt_seq=(SELECT COALESCE(MAX(last_attempt_seq),0)+1 FROM submissions) WHERE id=?',(sid,))
            tenant,payload,profile,owner,kind,cid,_,stored_digest,binding_text=row
            try:
                current=check(root,Path(owner)) if owner else check_registered(root,kind,cid)
                if canonical(current)!=profile:raise ValueError('Queued reporting profile is stale; explicit review/remap required')
                if digest(payload.encode())!=stored_digest:raise ValueError('Queued payload checksum mismatch')
                binding=json.loads(binding_text);validate_binding(root,binding,tenant,outbox)
                if Path(binding['sink_ref']).resolve()!=Path(ledger_db).resolve():raise ValueError('Delivery sink differs from bound sink')
                records=json.loads(payload);validate_bound_records(api,ledger_db,tenant,records,binding,current['component'])
                receipt=api['ingest'](ledger_db,tenant,records)
                receipt.update(submission_id=sid,payload_sha256=stored_digest,ledger_path=str(Path(ledger_db).resolve()),delivered_at=now())
                cx.execute('UPDATE submissions SET status=?,delivered_at=?,receipt=?,last_error=NULL WHERE id=?',('sent',receipt['delivered_at'],canonical(receipt),sid));cx.commit()
                results.append({'submission_id':sid,'status':'sent','receipt':receipt})
            except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:
                cx.execute('UPDATE submissions SET last_error=? WHERE id=?',(str(e),sid));cx.commit()
                results.append({'submission_id':sid,'status':'pending','error':str(e)})
    return {'attempted':len(results),'results':results,'all_attempts_delivered':bool(results) and all(x['status']=='sent' for x in results)}
def status(outbox,tenant):
    with closing(connect(outbox)) as cx:
        return [{'submission_id':r[0],'status':r[1],'queued_at':r[2],'delivered_at':r[3],'receipt':json.loads(r[4]) if r[4] else None,'last_error':r[5]} for r in cx.execute('SELECT id,status,queued_at,delivered_at,receipt,last_error FROM submissions WHERE tenant=? ORDER BY rowid',(tenant,))]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--framework-root',default=str(ROOT));p.add_argument('--outbox',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('enqueue');q.add_argument('--tenant',required=True);q.add_argument('--batch-key',required=True);q.add_argument('--input',required=True);q.add_argument('--binding',required=True)
    g=q.add_mutually_exclusive_group(required=True);g.add_argument('--component-dir');g.add_argument('--registered',help='agent:ID or skill:ID')
    f=sub.add_parser('flush');f.add_argument('--db',required=True);f.add_argument('--limit',type=int,default=100)
    s=sub.add_parser('status');s.add_argument('--tenant',required=True)
    a=p.parse_args();root=Path(a.framework_root).resolve()
    if a.command=='enqueue':
        with open(a.input,encoding='utf-8-sig') as stream:data=[json.loads(line) for line in stream if line.strip()]
        kind,cid=(a.registered.split(':',1) if a.registered and ':' in a.registered else (None,None))
        if a.registered and kind not in {'agent','skill'}:raise ValueError('Registered component must be agent:ID or skill:ID')
        result=enqueue(root,a.outbox,a.tenant,a.batch_key,data,read(a.binding),Path(a.component_dir).resolve() if a.component_dir else None,kind,cid)
    elif a.command=='flush':result=flush(root,a.outbox,a.db,a.limit)
    else:result=status(a.outbox,a.tenant)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    try:main()
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:print(str(e),file=sys.stderr);sys.exit(1)
