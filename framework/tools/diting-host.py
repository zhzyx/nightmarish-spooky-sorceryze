"""Explicit host event intake and federated Diting reads. No listener or timer."""
import argparse, hashlib, json, os, runpy, sqlite3, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing

def now(): return datetime.now(timezone.utc).isoformat()
def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v): return hashlib.sha256(v).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def resolve(root, value):
    if not isinstance(value,str) or not value or Path(value).is_absolute(): raise ValueError('Relative workspace path required')
    p=(root/value).resolve();p.relative_to(root)
    return p
def config(file):
    file=Path(file).resolve();c=read(file)
    if c.get('path_base')!='project_root' or c.get('project_root')!='..': raise ValueError('Catalog must be in project data-collection directory')
    root=file.parent.parent
    if file.parent.name!='data-collection':raise ValueError('Catalog location mismatch')
    for key in ('ledger','outbox','inbox','receipts','framework'):resolve(root,c[key])
    for key in ('ledger','outbox','inbox','receipts'):
        target=resolve(root,c[key]);target.relative_to(file.parent)
        if target==file.parent or target==file:raise ValueError('Storage must be a distinct child of data-collection')
    paths=[resolve(root,c[k]) for k in ('ledger','outbox','inbox','receipts')]
    if len(set(paths))!=4:raise ValueError('Storage paths must be distinct')
    return root,c
def atomic(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.tmp-'+os.urandom(8).hex())
    try:
        temp.write_text(canonical(value)+'\n',encoding='utf-8');os.replace(temp,p)
    finally:
        if temp.exists():temp.unlink()
def initialize(file):
    root,c=config(file);db=resolve(root,c['ledger']);db.parent.mkdir(parents=True,exist_ok=True)
    api=runpy.run_path(str(resolve(root,c['framework'])/'agents/diting/scripts/ledger.py'))
    if not db.exists():api['initialize'](db)
    return {'initialized':True,'ledger':c['ledger'],'runtime_authority_granted':False}
def submit(file,envelope):
    root,c=config(file)
    if envelope.get('tenant_id')!=c['tenant_id']:raise ValueError('Tenant mismatch')
    for key in ('batch_key','source_ref','agent_snapshot_ref','request_ref','authority_ref'):
        if not isinstance(envelope.get(key),str) or not envelope[key].strip():raise ValueError('Missing envelope '+key)
    if not isinstance(envelope.get('records'),list) or not envelope['records']:raise ValueError('Records required')
    authority=resolve(root,envelope['authority_ref'])
    if not authority.is_file():raise ValueError('Authority evidence missing')
    identity=sha(canonical([c['tenant_id'],envelope['batch_key']]).encode())
    inbox=resolve(root,c['inbox']);inbox.mkdir(parents=True,exist_ok=True)
    saved=inbox/(identity+'.json');lock=inbox/(identity+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        if saved.exists():
            if canonical(read(saved))!=canonical(envelope):raise ValueError('Event identity reused with different payload')
        else:atomic(saved,envelope)
        result={'batch_key':envelope['batch_key'],'envelope_sha256':sha(canonical(envelope).encode()),'recorded':True,'queued':False,'delivered':False,'path_base':'project_root','observed_at':now()}
        try:
            reporter=runpy.run_path(str(resolve(root,c['framework'])/'tools/diting-report.py'))
            outbox=resolve(root,c['outbox']);outbox.parent.mkdir(parents=True,exist_ok=True)
            binding={k:envelope[k] for k in ('tenant_id','source_ref','agent_snapshot_ref','request_ref','authority_ref')}
            binding.update(template=False,outbox_path=str(outbox),sink_ref=str(resolve(root,c['ledger'])))
            q=reporter['enqueue'](resolve(root,c['framework']),outbox,c['tenant_id'],envelope['batch_key'],envelope['records'],binding,kind='skill',cid=c['reporting_skill'])
            result.update(queued=True,submission_id=q['submission_id'])
            reporter['flush'](resolve(root,c['framework']),outbox,resolve(root,c['ledger']))
            receipt=next(x for x in reporter['status'](outbox,c['tenant_id']) if x['submission_id']==q['submission_id'])
            result.update(delivered=receipt['status']=='sent',receipt=receipt)
            if not result['delivered']:result['error']=receipt['last_error']
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:result['error']=str(e)
        result['outcome']='delivered' if result['delivered'] else 'pending_recovery'
        result['next_action']=None if result['delivered'] else 'Replay this exact envelope on an actual event; continue unrelated authorized work'
        atomic(resolve(root,c['receipts'])/(identity+'.json'),result)
        return result
    finally:os.close(fd);lock.unlink()

def query(file,tenant,work=None,kind=None):
    root,c=config(file)
    if tenant!=c['tenant_id']:raise ValueError('Tenant not registered')
    unique={};errors=[];snapshots=[];conflicts=set();replacements={}
    for source in c['sources']:
        try:
            db=resolve(root,source['path'])
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as cx:
                cx.execute('BEGIN')
                if cx.execute('pragma user_version').fetchone()[0]!=2:raise ValueError('Not a v2 ledger')
                rows=cx.execute('select id,digest,document,ingested_at from records where tenant=? order by id',(tenant,)).fetchall()
                # Use the original validity logic; never count superseded/stale facts as current.
                api=runpy.run_path(str(resolve(root,c['framework'])/'agents/diting/scripts/ledger.py'))
                snapshots.append({'path':source['path'],'records':len(rows),'snapshot_sha256':sha(canonical([[r[0],r[1]] for r in rows]).encode())})
                for rid,digest,doc,at in rows:
                    record=json.loads(doc);key=(tenant,rid)
                    if sha(canonical(record).encode())!=digest:
                        unique.pop(key,None);conflicts.add(key);errors.append({'source':source['path'],'error':'Record checksum mismatch: '+rid});continue
                    if record.get('supersedes'):replacements.setdefault(record['supersedes'],set()).add(rid)
                    if key in conflicts:continue
                    if key in unique:
                        if unique[key]['sha256']!=digest:
                            del unique[key];conflicts.add(key)
                            errors.append({'source':source['path'],'error':'Conflicting record excluded: '+rid})
                        continue
                    unique[key]={'record':record,'sha256':digest,'ingested_at':at,'state':api['evidence_state'](cx,tenant,rid),'source':source['path']}
        except (ValueError,KeyError,OSError,sqlite3.Error) as e:errors.append({'source':source.get('path'),'error':str(e)})
    # Resolve validity against the merged evidence graph, not whichever source was read first.
    for old,successors in replacements.items():
        if len(successors)>1:
            conflicts.update((tenant,rid) for rid in successors)
            errors.append({'source':'merged_evidence','error':'Conflicting successor versions: '+old})
    invalid_memo={}
    def invalid(rid,seen=None):
        if (tenant,rid) in conflicts:return True
        if rid in invalid_memo:return invalid_memo[rid]
        seen=set() if seen is None else set(seen)
        if rid in seen:return False
        seen.add(rid);v=unique.get((tenant,rid))
        if v is None:return True
        r=v['record'];ctx=r.get('context',{})
        refs=[*r['evidence_refs'],*ctx.get('related_agent_refs',[])]
        refs += [ctx[k] for k in ('request_ref','primary_agent_ref') if ctx.get(k) and ctx[k]!=rid]
        if r.get('supersedes'):refs.append(r['supersedes'])
        result=any(invalid(x,seen) for x in refs)
        invalid_memo[rid]=result;return result
    def state(rid,seen=None):
        if invalid(rid):return 'unavailable'
        if replacements.get(rid):return 'superseded'
        r=unique[(tenant,rid)]['record'];seen=set() if seen is None else set(seen)
        if rid in seen:return 'stale'
        seen.add(rid)
        if r['kind'] in ('annotation','classification','analysis','optimization','reference'):
            if any(state(x,seen)!='current' for x in r['evidence_refs']):return 'stale'
        return 'current'
    for (tenant_key,rid),v in unique.items():v['state']=state(rid)
    if any(v['state']=='unavailable' for v in unique.values()):errors.append({'source':'merged_evidence','error':'Records with missing or conflicting evidence excluded from current counts'})
    selected=[v for v in unique.values() if (not kind or v['record']['kind']==kind) and (not work or any(w['id']==work for w in v['record'].get('context',{}).get('work_items',[])))]
    counts={}
    for v in selected:
        if v['state']=='current':counts[v['record']['kind']]=counts.get(v['record']['kind'],0)+1
    return {'path_base':'project_root','generated_at':now(),'filters':{'tenant':tenant,'work':work,'kind':kind},'sources':snapshots,'source_errors':errors,'outcome':'partial' if errors else 'read','current_counts':counts,'records':selected,'coverage_note':'Only registered sources and observed facts; absent events are not proof that nothing happened','snapshot_sha256':sha(canonical([[v['record']['record_id'],v['sha256'],v['state']] for v in selected]).encode())}

def run_command(file,session,key,command):
    """Observe one explicitly supplied host command, without shell or authority escalation."""
    if not command:raise ValueError('Explicit command argv required')
    root,c=config(file);s=read(session)
    stable=sha(canonical([s['request_ref'],key]).encode())
    marker=resolve(root,c['receipts'])/('command-'+stable+'.json')
    marker.parent.mkdir(parents=True,exist_ok=True)
    # Never repeat an external effect merely because its collection receipt failed.
    fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(fd,'w',encoding='utf-8') as out:out.write(canonical({'status':'claimed','key':key,'command_sha256':sha(canonical(command).encode())}))
    started=now();base=s['request_ref']+':command:'+stable
    usage={'scope':'exclusive','usage_key':base,'provider':'unknown','model':'unknown','metering_ref':marker.relative_to(root).as_posix(),'equivalents':[]}
    for k in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens','reasoning_output_tokens'):usage[k]={'value':None,'status':'unavailable','reason':'Provider metering not supplied to command observer','method':'no estimate'}
    def step(suffix,status,end=None):
        r={'schema_version':2,'record_id':base+suffix,'tenant_id':s['tenant_id'],'kind':'step','created_at':now(),'evidence_refs':[s['source_ref']],'context':s['context'],'payload':{'source_key':s['source_key'],'event_key':base,'source_revision':'1' if not suffix else '2','step_key':base,'phase':key,'started_at':started,'ended_at':end,'duration_ms':None if end is None else (datetime.fromisoformat(end)-datetime.fromisoformat(started)).total_seconds()*1000,'status':status,'attempt':1,'trace_id':sha(s['request_ref'].encode())[:32],'span_id':stable[:16],'parent_step_ref':None,'usage':usage}}
        if suffix:r['supersedes']=base
        return r
    def send(suffix,record):return submit(file,{**{k:s[k] for k in ('tenant_id','source_ref','agent_snapshot_ref','request_ref','authority_ref')},'batch_key':base+suffix,'records':[record]})
    begin=send('',step('','running'))
    if not begin['delivered']:
        atomic(marker,{'status':'not_executed','begin':begin});return {'status':'not_executed','reason':'Start receipt requires recovery; use a new command key after reconciliation'}
    try:
        result=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace')
        status='succeeded' if result.returncode==0 else 'failed';code=result.returncode
        print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
    except OSError as e:status='failed';code=None;print(str(e),file=sys.stderr)
    ended=now();terminal=step(':end',status,ended)
    terminal['payload']['exit_code']=code
    atomic(marker,{'status':status,'exit_code':code,'terminal_record':terminal,'end_receipt':'pending'})
    finish=send(':end',terminal)
    atomic(marker,{'status':status,'exit_code':code,'terminal_record':terminal,'end_receipt':finish})
    return {'status':status,'exit_code':code,'outcome':'delivered' if finish['delivered'] else 'pending_recovery','start_delivered':True,'end_delivered':finish['delivered'],'evidence':marker.relative_to(root).as_posix(),'repeat_command':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog',required=True)
    sub=p.add_subparsers(dest='command',required=True);sub.add_parser('init')
    s=sub.add_parser('submit');s.add_argument('--envelope',required=True)
    q=sub.add_parser('query');q.add_argument('--tenant',required=True);q.add_argument('--work');q.add_argument('--kind');q.add_argument('--receipt')
    run=sub.add_parser('run');run.add_argument('--session',required=True);run.add_argument('--key',required=True);run.add_argument('argv',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if a.command=='init':r=initialize(a.catalog)
    elif a.command=='submit':r=submit(a.catalog,read(a.envelope))
    elif a.command=='run':r=run_command(a.catalog,a.session,a.key,a.argv[1:] if a.argv[:1]==['--'] else a.argv)
    else:
        r=query(a.catalog,a.tenant,a.work,a.kind)
        if a.receipt:
            root,c=config(a.catalog);target=resolve(root,a.receipt)
            target.relative_to(resolve(root,c['receipts']))
            atomic(target,r)
    print(json.dumps(r,ensure_ascii=False))
    if r.get('outcome') in ('pending_recovery','partial'):return 2
    if r.get('status') in ('failed','not_executed'):return 1
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,KeyError,OSError,sqlite3.Error) as e:print(str(e),file=sys.stderr);sys.exit(1)
